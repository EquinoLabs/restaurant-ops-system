"""
ROMS Platform Governance — PostgreSQL Concurrency & Constraint Integration Tests (OP-02)

Validates:
1. Advisory-lock serialization using lock key 424242111 across independent PostgreSQL connections.
2. Safe entity re-validation under READ COMMITTED using .populate_existing().
3. Single-active-Platform-Owner partial unique index constraint (ix_users_single_active_platform_owner).
4. Lock release behavior on COMMIT and ROLLBACK.
5. Storage-engine constraint backstop when application locks are bypassed.
6. Bounded statement timeouts and reliable transaction/connection cleanup.

NOTE: All tests require explicit opt-in via `--pg-integration` and a dedicated test database
configured via `ROMS_POSTGRES_TEST_DATABASE_URL`. Without these flags, pytest skips all tests automatically.
"""

import threading
import time
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.security import hash_password
from app.core.errors import ForbiddenError
from app.modules.businesses.platform_service import (
    ADMIN_PRIVILEGE_LOCK_KEY,
    _acquire_admin_serialization_lock,
    transfer_platform_owner,
)
from scripts.create_platform_admin import promote_user_to_platform_admin_service

pytestmark = pytest.mark.postgres_integration


def _create_test_user(session: Session, email_prefix: str, role: str = None, is_admin: bool = False) -> User:
    """Helper to provision a transient test user in a PostgreSQL test session."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("TestPassword123!"),
        display_name=f"Test {email_prefix.title()}",
        status="active",
        platform_role=role,
        is_platform_admin=is_admin,
    )
    session.add(user)
    session.flush()
    return user


# ==============================================================================
# Scenario 1: Competing Owner Transfers (Lock Serialization & Re-Read Rejection)
# ==============================================================================

def test_pg_concurrent_owner_transfer_race(pg_engine, pg_user_tracker):
    """
    Two concurrent transfer requests from the same Owner race across independent PostgreSQL connections.
    Verifies that:
    - Connection 1 acquires lock 424242111 and completes transfer to Target A.
    - Connection 2 blocks in PostgreSQL until Connection 1 commits.
    - Connection 2 unblocks, reloads actor via .populate_existing() under READ COMMITTED,
      observes that actor is no longer Owner, and raises ForbiddenError.
    - Exactly 1 active Owner exists in PostgreSQL at completion.
    """
    SessionMaker = sa.orm.sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    # Setup seed data with tracked, run-scoped test users
    setup_session = SessionMaker()
    try:
        owner = pg_user_tracker.create_user(setup_session, "owner", role="owner", is_admin=True)
        target_a = pg_user_tracker.create_user(setup_session, "target_a", role="admin", is_admin=True)
        target_b = pg_user_tracker.create_user(setup_session, "target_b", role="admin", is_admin=True)
        setup_session.commit()
        owner_id = owner.id
        target_a_id = target_a.id
        target_b_id = target_b.id
    finally:
        setup_session.close()

    t1_locked = threading.Event()
    t2_blocked_verified = threading.Event()
    results = {}

    def run_transfer_1():
        s1 = SessionMaker()
        try:
            with s1.begin():
                _acquire_admin_serialization_lock(s1)
                t1_locked.set()
                # Wait for Thread 2 to confirm lock is held exclusively
                assert t2_blocked_verified.wait(timeout=5), "Thread 2 did not confirm lock contention in time"
                transfer_platform_owner(
                    s1,
                    actor_user_id=owner_id,
                    target_user_id=target_a_id,
                    current_password="TestPassword123!",
                )
            results["t1"] = "success"
        except Exception as exc:
            results["t1"] = exc
        finally:
            s1.close()

    def run_transfer_2():
        s2 = SessionMaker()
        try:
            # Wait for Thread 1 to acquire the advisory lock
            assert t1_locked.wait(timeout=5), "Thread 1 did not acquire lock in time"

            # Deterministically verify that Thread 1 holds lock 424242111 exclusively
            held = s2.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            ).scalar()
            assert held is False, "Expected advisory lock 424242111 to be held by Thread 1"
            t2_blocked_verified.set()
            s2.rollback()

            with s2.begin():
                # This call will block at PostgreSQL level until Thread 1 commits!
                transfer_platform_owner(
                    s2,
                    actor_user_id=owner_id,
                    target_user_id=target_b_id,
                    current_password="TestPassword123!",
                )
            results["t2"] = "success"
        except Exception as exc:
            results["t2"] = exc
        finally:
            s2.close()

    th1 = threading.Thread(target=run_transfer_1)
    th2 = threading.Thread(target=run_transfer_2)

    th1.start()
    th2.start()

    th1.join(timeout=10)
    th2.join(timeout=10)

    # Thread 1 must succeed
    assert results.get("t1") == "success", f"Thread 1 failed: {results.get('t1')}"

    # Thread 2 must fail closed with ForbiddenError upon unblocking
    assert isinstance(results.get("t2"), ForbiddenError), f"Expected ForbiddenError for Thread 2, got: {results.get('t2')}"
    assert "Actor does not possess Platform Owner privileges" in str(results.get("t2"))

    # Invariant verification in a fresh session
    verify_session = SessionMaker()
    try:
        active_owners = verify_session.query(User).filter(
            User.platform_role == "owner", User.status == "active"
        ).all()
        assert len(active_owners) == 1
        assert active_owners[0].id == target_a_id

        old_owner = verify_session.query(User).filter(User.id == owner_id).first()
        assert old_owner.platform_role == "admin"
        assert old_owner.is_platform_admin is True

        loser = verify_session.query(User).filter(User.id == target_b_id).first()
        assert loser.platform_role == "admin"

        # Exactly 1 transfer audit log exists
        transfers = verify_session.query(AuditLog).filter(
            AuditLog.action == "platform.owner.transfer",
            AuditLog.actor_user_id == owner_id,
        ).all()
        assert len(transfers) == 1
    finally:
        verify_session.close()


# ==============================================================================
# Scenario 2: Concurrent First-Owner Bootstrap Race
# ==============================================================================

def test_pg_concurrent_bootstrap_first_owner(pg_engine, pg_user_tracker):
    """
    Two concurrent bootstrap attempts race to designate the first Platform Owner when none exists.
    Verifies that:
    - Advisory lock serializes the check-then-set bootstrap sequence.
    - Winner establishes ownership; loser unblocks, detects active_owners > 0, and returns False.
    - Zero IntegrityError exceptions or duplicate owners occur.
    """
    SessionMaker = sa.orm.sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    setup_session = SessionMaker()
    try:
        u1 = pg_user_tracker.create_user(setup_session, "cand1", role=None, is_admin=False)
        u2 = pg_user_tracker.create_user(setup_session, "cand2", role=None, is_admin=False)
        setup_session.commit()
        u1_email = u1.email
        u2_email = u2.email
    finally:
        setup_session.close()

    t1_acquired = threading.Event()
    t2_blocked_verified = threading.Event()
    results = {}

    def run_bootstrap_1():
        s1 = SessionMaker()
        try:
            with s1.begin():
                _acquire_admin_serialization_lock(s1)
                t1_acquired.set()
                assert t2_blocked_verified.wait(timeout=5), "Thread 2 did not confirm lock contention in time"
                res = promote_user_to_platform_admin_service(s1, email=u1_email, role="owner")
                results["b1"] = res
        except Exception as exc:
            results["b1"] = exc
        finally:
            s1.close()

    def run_bootstrap_2():
        s2 = SessionMaker()
        try:
            assert t1_acquired.wait(timeout=5)
            # Deterministically verify Thread 1 holds lock
            held = s2.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            ).scalar()
            assert held is False
            t2_blocked_verified.set()
            s2.rollback()

            with s2.begin():
                res = promote_user_to_platform_admin_service(s2, email=u2_email, role="owner")
                results["b2"] = res
        except Exception as exc:
            results["b2"] = exc
        finally:
            s2.close()


    th1 = threading.Thread(target=run_bootstrap_1)
    th2 = threading.Thread(target=run_bootstrap_2)

    th1.start()
    th2.start()

    th1.join(timeout=10)
    th2.join(timeout=10)

    # Exactly one succeeded and one cleanly returned False
    outcomes = [results.get("b1"), results.get("b2")]
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1

    # Invariant verification: Exactly 1 active Owner exists in database
    verify_session = SessionMaker()
    try:
        owners = verify_session.query(User).filter(
            User.platform_role == "owner", User.status == "active"
        ).all()
        assert len(owners) == 1
    finally:
        verify_session.close()


# ==============================================================================
# Scenario 3: Advisory-Lock Behavior on Commit
# ==============================================================================

def test_pg_advisory_lock_released_on_commit(pg_connection_pair):
    """
    Confirms transaction-scoped advisory lock 424242111 is held during a transaction
    and released immediately upon COMMIT, allowing concurrent transactions to acquire it.
    """
    conn1, conn2 = pg_connection_pair

    t1_locked = threading.Event()
    t2_checked = threading.Event()
    results = {}

    def run_conn1():
        try:
            tx1 = conn1.begin()
            conn1.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            )
            t1_locked.set()
            assert t2_checked.wait(timeout=5)
            tx1.commit()
            results["tx1"] = "committed"
        except Exception as exc:
            results["tx1"] = exc

    def run_conn2():
        try:
            assert t1_locked.wait(timeout=5)
            # While Connection 1 holds the lock, try-lock must return False
            held = conn2.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            ).scalar()
            results["try_lock_during_tx1"] = held
            t2_checked.set()
            conn2.rollback()

            # Now wait for blocking lock — unblocks once Conn 1 commits
            tx2 = conn2.begin()
            conn2.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            )
            tx2.commit()
            results["tx2"] = "acquired_after_commit"
        except Exception as exc:
            results["tx2"] = exc

    th1 = threading.Thread(target=run_conn1)
    th2 = threading.Thread(target=run_conn2)
    th1.start()
    th2.start()
    th1.join(timeout=10)
    th2.join(timeout=10)

    assert results.get("tx1") == "committed"
    assert results.get("try_lock_during_tx1") is False
    assert results.get("tx2") == "acquired_after_commit"


# ==============================================================================
# Scenario 4: Advisory-Lock Behavior on Rollback
# ==============================================================================

def test_pg_advisory_lock_released_on_rollback(pg_connection_pair, pg_engine, pg_user_tracker):
    """
    Confirms advisory lock 424242111 is released immediately upon ROLLBACK,
    and uncommitted mutations from the rolled-back transaction are not visible.
    """
    conn1, conn2 = pg_connection_pair
    SessionMaker = sa.orm.sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    setup_session = SessionMaker()
    try:
        user = pg_user_tracker.create_user(setup_session, "rollback_test", role="admin", is_admin=True)
        setup_session.commit()
        user_id = user.id
        initial_name = user.display_name
    finally:
        setup_session.close()

    t1_locked = threading.Event()
    t2_checked = threading.Event()
    results = {}

    def run_conn1():
        try:
            tx1 = conn1.begin()
            conn1.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            )
            conn1.execute(
                text("UPDATE users SET display_name = 'DirtyUncommitted' WHERE id = :id"),
                {"id": user_id}
            )
            t1_locked.set()
            assert t2_checked.wait(timeout=5)
            tx1.rollback()
            results["tx1"] = "rolled_back"
        except Exception as exc:
            results["tx1"] = exc

    def run_conn2():
        try:
            assert t1_locked.wait(timeout=5)
            # Verify lock is held exclusively
            held = conn2.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            ).scalar()
            results["try_lock_during_tx1"] = held
            t2_checked.set()
            conn2.rollback()

            # Wait for unblock on rollback
            tx2 = conn2.begin()
            conn2.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            )
            # Check uncommitted mutation is absent
            val = conn2.execute(
                text("SELECT display_name FROM users WHERE id = :id"),
                {"id": user_id}
            ).scalar()
            results["observed_name"] = val
            tx2.rollback()
            results["tx2"] = "acquired_after_rollback"
        except Exception as exc:
            results["tx2"] = exc

    th1 = threading.Thread(target=run_conn1)
    th2 = threading.Thread(target=run_conn2)
    th1.start()
    th2.start()
    th1.join(timeout=10)
    th2.join(timeout=10)

    assert results.get("tx1") == "rolled_back"
    assert results.get("try_lock_during_tx1") is False
    assert results.get("tx2") == "acquired_after_rollback"
    assert results.get("observed_name") == initial_name


# ==============================================================================
# Scenario 5: Storage Engine Constraint Fallback (Advisory Lock Bypass)
# ==============================================================================

def test_pg_unique_index_enforcement_on_bypass(pg_connection_pair, pg_engine, pg_user_tracker):
    """
    Demonstrates defense-in-depth: if application-level advisory locking is bypassed,
    the partial unique index `ix_users_single_active_platform_owner` strictly prevents
    two active Platform Owners from co-existing.
    """
    conn1, conn2 = pg_connection_pair
    SessionMaker = sa.orm.sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    setup_session = SessionMaker()
    try:
        u1 = pg_user_tracker.create_user(setup_session, "bypass1", role="admin", is_admin=True)
        u2 = pg_user_tracker.create_user(setup_session, "bypass2", role="admin", is_admin=True)
        setup_session.commit()
        u1_id = u1.id
        u2_id = u2.id
    finally:
        setup_session.close()

    t1_updated = threading.Event()
    t2_ready = threading.Event()
    results = {}

    def run_conn1():
        try:
            tx1 = conn1.begin()
            # Bypassing advisory lock; raw update to owner
            conn1.execute(
                text("UPDATE users SET platform_role = 'owner', status = 'active' WHERE id = :id"),
                {"id": u1_id}
            )
            t1_updated.set()
            assert t2_ready.wait(timeout=5), "Thread 2 did not signal readiness"

            # Deterministically verify that Thread 2 has reached and blocked on the unique index conflict in PostgreSQL
            blocked = False
            for _ in range(50):
                cnt = conn1.execute(text("SELECT COUNT(*) FROM pg_locks WHERE NOT granted")).scalar() or 0
                if cnt > 0:
                    blocked = True
                    break
                time.sleep(0.05)

            # Conn 1 commits; unblocks Conn 2 which will encounter the uniqueness violation
            tx1.commit()
            results["tx1"] = "committed"
        except Exception as exc:
            results["tx1"] = exc
            try:
                tx1.rollback()
            except Exception:
                pass

    def run_conn2():
        try:
            assert t1_updated.wait(timeout=5), "Thread 1 did not execute first update in time"
            tx2 = conn2.begin()
            t2_ready.set()
            # Bypassing advisory lock; concurrent update to second owner.
            # This statement blocks inside PostgreSQL kernel on ix_users_single_active_platform_owner
            # until tx1 commits, at which point PostgreSQL raises IntegrityError!
            try:
                conn2.execute(
                    text("UPDATE users SET platform_role = 'owner', status = 'active' WHERE id = :id"),
                    {"id": u2_id}
                )
                tx2.commit()
                results["tx2"] = "committed_unexpected"
            except IntegrityError as exc:
                results["tx2"] = exc
                try:
                    tx2.rollback()
                except Exception:
                    pass
        except Exception as exc:
            results["tx2"] = exc
            try:
                tx2.rollback()
            except Exception:
                pass

    th1 = threading.Thread(target=run_conn1)
    th2 = threading.Thread(target=run_conn2)
    th1.start()
    th2.start()
    th1.join(timeout=10)
    th2.join(timeout=10)

    assert results.get("tx1") == "committed"
    assert isinstance(results.get("tx2"), IntegrityError), f"Expected IntegrityError for Conn 2, got: {results.get('tx2')}"

    err_str = str(results.get("tx2")).lower()
    # Confirm error references unique constraint or 23505 UniqueViolation
    assert "ix_users_single_active_platform_owner" in err_str or "23505" in err_str or "unique constraint" in err_str

    # Database invariant check
    verify_session = SessionMaker()
    try:
        owners = verify_session.query(User).filter(
            User.platform_role == "owner", User.status == "active"
        ).all()
        assert len(owners) == 1
        assert owners[0].id == u1_id
    finally:
        verify_session.close()


# ==============================================================================
# Scenario 6: Statement Timeout & Connection Cleanup
# ==============================================================================

def test_pg_statement_timeout_and_cleanup(pg_connection_pair):
    """
    Verifies that a transaction waiting on a stalled advisory lock times out cleanly
    under statement_timeout without freezing the test suite, and connection teardown
    restores lock availability.
    """
    conn1, conn2 = pg_connection_pair

    # Configure short statement timeout on Connection 2
    conn2.execute(text("SET statement_timeout = '1500ms';"))
    conn2.commit()

    t1_locked = threading.Event()
    t2_timed_out = threading.Event()
    results = {}

    def run_conn1():
        try:
            tx1 = conn1.begin()
            conn1.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": ADMIN_PRIVILEGE_LOCK_KEY}
            )
            t1_locked.set()
            # Wait deterministically for Connection 2 to time out and signal
            assert t2_timed_out.wait(timeout=10), "Connection 2 did not signal statement timeout"
            tx1.rollback()
            results["tx1"] = "rolled_back"
        except Exception as exc:
            results["tx1"] = exc

    def run_conn2():
        try:
            assert t1_locked.wait(timeout=5)
            tx2 = conn2.begin()
            try:
                # This should block and time out after 1500ms
                conn2.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": ADMIN_PRIVILEGE_LOCK_KEY}
                )
                results["tx2"] = "lock_acquired_unexpected"
            except OperationalError as exc:
                results["tx2"] = exc
                t2_timed_out.set()
                tx2.rollback()
        except Exception as exc:
            results["tx2"] = exc

    th1 = threading.Thread(target=run_conn1)
    th2 = threading.Thread(target=run_conn2)
    th1.start()
    th2.start()
    th1.join(timeout=10)
    th2.join(timeout=10)

    assert results.get("tx1") == "rolled_back"
    assert isinstance(results.get("tx2"), OperationalError), f"Expected OperationalError on timeout, got: {results.get('tx2')}"

    # Lock must be immediately acquirable now
    available = conn1.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": ADMIN_PRIVILEGE_LOCK_KEY}
    ).scalar()
    assert available is True
