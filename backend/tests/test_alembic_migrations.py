import os
import importlib.util
import pytest

def load_migration_module(filename: str):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "alembic", "versions", filename)
    spec = importlib.util.spec_from_file_location("migration_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_alembic_migration_0008_structure():
    m0008 = load_migration_module("0008_order_idempotency_keys.py")
    assert m0008.revision == '0008_order_idempotency_keys'
    assert m0008.down_revision == '0007_audit_log_biz_id_nullable'
    assert callable(m0008.upgrade)
    assert callable(m0008.downgrade)

def test_alembic_migration_0009_structure():
    m0009 = load_migration_module("0009_order_number_unique.py")
    assert m0009.revision == '0009_order_number_unique'
    assert m0009.down_revision == '0008_order_idempotency_keys'
    assert callable(m0009.upgrade)
    assert callable(m0009.downgrade)

def test_alembic_migration_0010_structure():
    m0010 = load_migration_module("0010_subscription_entitlements.py")
    assert m0010.revision == '0010_subscription_entitlements'
    assert m0010.down_revision == '0009_order_number_unique'
    assert callable(m0010.upgrade)
    assert callable(m0010.downgrade)

def test_migration_0010_precheck_aborts(monkeypatch):
    import uuid
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0010 = load_migration_module("0010_subscription_entitlements.py")
    
    # Create temp SQLite DB with businesses table
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE businesses ("
            "id CHAR(36) PRIMARY KEY, "
            "name VARCHAR(200) NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "subscription_status VARCHAR(20) NOT NULL, "
            "plan_name VARCHAR(50), "
            "max_outlets INTEGER, "
            "trial_ends_at DATETIME"
            ")"
        ))
        unmapped_id = str(uuid.uuid4())
        conn.execute(sa.text(
            "INSERT INTO businesses (id, name, status, subscription_status, plan_name) "
            "VALUES (:id, 'Test Biz', 'active', 'trial', 'unsupported_custom_plan')"
        ), {'id': unmapped_id})

    # Mock op.get_bind() to return our engine connection
    with engine.connect() as conn:
        monkeypatch.setattr(m0010.op, "get_bind", lambda: conn)
        with pytest.raises(RuntimeError) as exc_info:
            m0010.upgrade()

        err_msg = str(exc_info.value)
        assert "Migration 0010 aborted" in err_msg
        assert "unmapped plan_name values" in err_msg
        assert unmapped_id in err_msg
        assert "unsupported_custom_plan" in err_msg


def test_alembic_migration_0011_structure():
    m0011 = load_migration_module("0011_add_platform_role_column.py")
    assert m0011.revision == '0011_add_platform_role_column'
    assert m0011.down_revision == '0010_subscription_entitlements'
    assert callable(m0011.upgrade)
    assert callable(m0011.downgrade)


def test_migration_0011_upgrade_and_downgrade_execution():
    """
    Validates migration 0011 upgrade and downgrade execution against an isolated SQLite test database.

    Verifies:
    1. users.platform_role column is added as nullable String(20).
    2. Index ix_users_platform_role is created (non-unique).
    3. Pre-existing user rows and fields survive intact with platform_role IS NULL (no premature backfill).
    4. Migration 0011 adds zero check constraints or unique indexes (unconstrained expansion).
    5. downgrade() drops platform_role and ix_users_platform_role, preserving pre-existing data.

    PostgreSQL Validation Limitation:
    SQLite does not enforce or validate PostgreSQL-specific transactional advisory locks
    or partial unique index expressions. True PostgreSQL concurrency and constraint
    serialization requires the dedicated PostgreSQL integration test suite.
    """
    import sqlalchemy as sa
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    m0011 = load_migration_module("0011_add_platform_role_column.py")

    engine = create_engine("sqlite:///:memory:")
    conn = engine.connect()

    try:
        # 1. Setup isolated users table matching revision 0010 schema
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(150) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                is_platform_admin BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))

        # 2. Seed representative pre-existing users (legacy admin and staff)
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, display_name, status, is_platform_admin, created_at, updated_at)
            VALUES
                ('u-admin', 'legacy_admin@test.com', 'hash_admin', 'Legacy Admin', 'active', 1, '2026-10-10 10:00:00', '2026-10-10 10:00:00'),
                ('u-staff', 'staff@test.com', 'hash_staff', 'Staff Member', 'active', 0, '2026-10-10 10:00:00', '2026-10-10 10:00:00')
        """))
        conn.commit()

        # 3. Configure Alembic operations context and execute upgrade()
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m0011.upgrade()

        insp = inspect(conn)

        # 4. Verify platform_role column properties
        columns = {c['name']: c for c in insp.get_columns('users')}
        assert "platform_role" in columns
        assert columns['platform_role']['nullable'] is True

        # 5. Verify index ix_users_platform_role exists and is non-unique
        indexes = {i['name']: i for i in insp.get_indexes('users')}
        assert "ix_users_platform_role" in indexes
        assert not indexes['ix_users_platform_role']['unique']
        assert indexes['ix_users_platform_role']['column_names'] == ['platform_role']

        # 6. Verify NO check constraints were added in this migration (expansion only)
        check_constraints = insp.get_check_constraints('users')
        assert len(check_constraints) == 0

        # 7. Verify pre-existing data survived intact and NO data backfill was performed
        admin_row = conn.execute(text(
            "SELECT email, is_platform_admin, platform_role FROM users WHERE id = 'u-admin'"
        )).fetchone()
        assert admin_row[0] == "legacy_admin@test.com"
        assert admin_row[1] == 1  # is_platform_admin preserved
        assert admin_row[2] is None  # platform_role NOT backfilled yet

        staff_row = conn.execute(text(
            "SELECT email, is_platform_admin, platform_role FROM users WHERE id = 'u-staff'"
        )).fetchone()
        assert staff_row[0] == "staff@test.com"
        assert staff_row[1] == 0
        assert staff_row[2] is None

        # 8. Execute downgrade()
        with Operations.context(ctx):
            m0011.downgrade()

        insp_post_down = inspect(conn)

        # 9. Verify column and index are dropped
        post_columns = [c['name'] for c in insp_post_down.get_columns('users')]
        assert "platform_role" not in post_columns

        post_indexes = [i['name'] for i in insp_post_down.get_indexes('users')]
        assert "ix_users_platform_role" not in post_indexes

        # 10. Verify pre-existing user data still intact after downgrade
        admin_post_down = conn.execute(text(
            "SELECT email, is_platform_admin FROM users WHERE id = 'u-admin'"
        )).fetchone()
        assert admin_post_down[0] == "legacy_admin@test.com"
        assert admin_post_down[1] == 1

    finally:
        conn.close()
        engine.dispose()


def test_alembic_migration_0012_structure():
    m0012 = load_migration_module("0012_platform_role_constraints.py")
    assert m0012.revision == '0012_platform_role_constraints'
    assert m0012.down_revision == '0011_add_platform_role_column'
    assert callable(m0012.upgrade)
    assert callable(m0012.downgrade)


def test_migration_0012_precheck_aborts_on_contradictory_roles(monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                status VARCHAR(20) NOT NULL,
                is_platform_admin BOOLEAN NOT NULL,
                platform_role VARCHAR(20)
            )
        """))
        # Seed contradictory operator with admin boolean flag
        conn.execute(sa.text("""
            INSERT INTO users (id, email, status, is_platform_admin, platform_role)
            VALUES ('u-bad-op', 'bad_op@test.com', 'active', 1, 'operator')
        """))

    with engine.connect() as conn:
        monkeypatch.setattr(m0012.op, "get_bind", lambda: conn)
        with pytest.raises(RuntimeError) as exc_info:
            m0012.upgrade()
        assert "Migration 0012 aborted" in str(exc_info.value)
        assert "corrupt, malformed, or contradictory" in str(exc_info.value)


def test_migration_0012_precheck_aborts_on_malformed_and_unsupported_roles(monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    # Test cases: empty string, whitespace-padded, case-variant, unsupported
    bad_roles = ['', ' admin', 'Owner', 'superadmin']
    for bad_role in bad_roles:
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    email VARCHAR(254) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    is_platform_admin BOOLEAN NOT NULL,
                    platform_role VARCHAR(20)
                )
            """))
            conn.execute(sa.text("""
                INSERT INTO users (id, email, status, is_platform_admin, platform_role)
                VALUES ('u-bad', 'bad@test.com', 'active', 1, :role)
            """), {'role': bad_role})

        with engine.connect() as conn:
            monkeypatch.setattr(m0012.op, "get_bind", lambda: conn)
            with pytest.raises(RuntimeError) as exc_info:
                m0012.upgrade()
            assert "Migration 0012 aborted" in str(exc_info.value)
            assert "corrupt, malformed, or contradictory" in str(exc_info.value)


def test_migration_0012_precheck_aborts_on_multiple_active_owners(monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                status VARCHAR(20) NOT NULL,
                is_platform_admin BOOLEAN NOT NULL,
                platform_role VARCHAR(20)
            )
        """))
        # Seed two active owners
        conn.execute(sa.text("""
            INSERT INTO users (id, email, status, is_platform_admin, platform_role)
            VALUES
                ('u-o1', 'owner1@test.com', 'active', 1, 'owner'),
                ('u-o2', 'owner2@test.com', 'active', 1, 'owner')
        """))

    with engine.connect() as conn:
        monkeypatch.setattr(m0012.op, "get_bind", lambda: conn)
        with pytest.raises(RuntimeError) as exc_info:
            m0012.upgrade()
        assert "Migration 0012 aborted" in str(exc_info.value)
        assert "Maximum allowed is 1" in str(exc_info.value)


def test_migration_0012_upgrade_and_downgrade_execution():
    """
    Validates migration 0012 upgrade, constraint enforcement, and downgrade execution.

    Verifies:
    1. Valid compliant users survive upgrade: ordinary user (NULL, 0), Admin ('admin', 1),
       Owner ('owner', 1), Operator ('operator', 0), Suspended Owner ('owner', 1).
    2. Legacy admin (NULL, 1) is backfilled to ('admin', 1).
    3. Consistency CHECK constraint rejects invalid combinations and unsupported role strings.
    4. Partial unique index rejects a second active Owner, but permits a suspended Owner.
    5. Downgrade removes the index and CHECK constraint, while preserving backfilled role data.
    """
    import sqlalchemy as sa
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.exc import IntegrityError
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    engine = create_engine("sqlite:///:memory:")
    conn = engine.connect()

    try:
        # 1. Setup users table matching revision 0011 schema
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL UNIQUE,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                is_platform_admin BOOLEAN NOT NULL DEFAULT 0,
                platform_role VARCHAR(20)
            )
        """))

        # 2. Seed compliant users and one eligible legacy admin
        conn.execute(text("""
            INSERT INTO users (id, email, status, is_platform_admin, platform_role)
            VALUES
                ('u-user', 'user@test.com', 'active', 0, NULL),
                ('u-admin', 'admin@test.com', 'active', 1, 'admin'),
                ('u-owner', 'owner@test.com', 'active', 1, 'owner'),
                ('u-op', 'operator@test.com', 'active', 0, 'operator'),
                ('u-legacy', 'legacy@test.com', 'active', 1, NULL),
                ('u-susp-owner', 'susp_owner@test.com', 'suspended', 1, 'owner')
        """))
        conn.commit()

        # 3. Execute upgrade()
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m0012.upgrade()
        conn.commit()

        # 4. Verify legacy admin was backfilled to 'admin'
        legacy_row = conn.execute(text(
            "SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-legacy'"
        )).fetchone()
        assert legacy_row[0] == 1
        assert legacy_row[1] == 'admin'

        # 5. Verify compliant users retained their exact state
        user_row = conn.execute(text("SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-user'")).fetchone()
        assert user_row[0] == 0 and user_row[1] is None

        admin_row = conn.execute(text("SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-admin'")).fetchone()
        assert admin_row[0] == 1 and admin_row[1] == 'admin'

        owner_row = conn.execute(text("SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-owner'")).fetchone()
        assert owner_row[0] == 1 and owner_row[1] == 'owner'

        op_row = conn.execute(text("SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-op'")).fetchone()
        assert op_row[0] == 0 and op_row[1] == 'operator'

        # 6. Verify CHECK constraint rejects invalid combination (e.g. admin with is_platform_admin=0)
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO users (id, email, status, is_platform_admin, platform_role) VALUES ('u-inv1', 'inv1@test.com', 'active', 0, 'admin')"))
            conn.commit()
        conn.rollback()

        # 7. Verify CHECK constraint rejects unsupported role
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO users (id, email, status, is_platform_admin, platform_role) VALUES ('u-inv2', 'inv2@test.com', 'active', 1, 'superadmin')"))
            conn.commit()
        conn.rollback()

        # 8. Verify partial unique index rejects a second active Owner
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO users (id, email, status, is_platform_admin, platform_role) VALUES ('u-o2', 'owner2@test.com', 'active', 1, 'owner')"))
            conn.commit()
        conn.rollback()

        # 9. Verify partial unique index PERMITS a non-active Owner (status='suspended')
        conn.execute(text("INSERT INTO users (id, email, status, is_platform_admin, platform_role) VALUES ('u-susp2', 'susp2@test.com', 'suspended', 1, 'owner')"))
        conn.commit()

        # 10. Execute downgrade()
        with Operations.context(ctx):
            m0012.downgrade()
        conn.commit()

        insp_post_down = inspect(conn)
        post_indexes = [i['name'] for i in insp_post_down.get_indexes('users')]
        assert "ix_users_single_active_platform_owner" not in post_indexes

        # 11. Verify backfilled data was PRESERVED across downgrade
        legacy_post_down = conn.execute(text(
            "SELECT is_platform_admin, platform_role FROM users WHERE id = 'u-legacy'"
        )).fetchone()
        assert legacy_post_down[0] == 1
        assert legacy_post_down[1] == 'admin'  # Not reversed!

    finally:
        conn.close()
        engine.dispose()


def test_migration_0012_postcheck_aborts_on_unreconciled_rows(monkeypatch):
    """
    Verifies that the migration fails closed at Step 5 (inline post-backfill check)
    if non-compliant records remain in the table after the Step 4 backfill UPDATE.
    """
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                status VARCHAR(20) NOT NULL,
                is_platform_admin BOOLEAN NOT NULL,
                platform_role VARCHAR(20)
            )
        """))
        # Seed an eligible legacy admin along with valid ordinary user and active owner.
        # The pre-check gates (Steps 2 and 3) accept this dataset without error.
        conn.execute(sa.text("""
            INSERT INTO users (id, email, status, is_platform_admin, platform_role)
            VALUES
                ('u-legacy', 'legacy@test.com', 'active', 1, NULL),
                ('u-user', 'user@test.com', 'active', 0, NULL),
                ('u-owner', 'owner@test.com', 'active', 1, 'owner')
        """))

    with engine.connect() as conn:
        real_execute = conn.execute
        update_intercepted = False

        def intercepted_execute(statement, *args, **kwargs):
            nonlocal update_intercepted
            stmt_str = str(statement)
            if "UPDATE users" in stmt_str and "SET platform_role = 'admin'" in stmt_str:
                update_intercepted = True
                # Intercept the backfill UPDATE and make it a no-op so the legacy row remains unreconciled
                return real_execute(sa.text("SELECT 1"))
            return real_execute(statement, *args, **kwargs)

        monkeypatch.setattr(conn, "execute", intercepted_execute)
        monkeypatch.setattr(m0012.op, "get_bind", lambda: conn)

        with pytest.raises(RuntimeError) as exc_info:
            m0012.upgrade()

        assert update_intercepted is True
        assert "Migration 0012 aborted: Post-backfill check failed" in str(exc_info.value)
        assert "Found 1 non-compliant rows" in str(exc_info.value)


def test_migration_0012_transaction_rollback_after_postcheck_failure(monkeypatch):
    """
    Verifies that when a migration failure occurs after the legacy backfill UPDATE,
    the owning transaction rolls back and restores modified rows to their original state.

    Transaction ownership:
    The transaction is explicitly started and owned by the test harness via `conn.begin()`.
    When Migration 0012 upgrade aborts at the post-backfill gate, the test harness explicitly
    calls `trans.rollback()`, confirming that the uncommitted UPDATE is cleanly undone.
    """
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0012 = load_migration_module("0012_platform_role_constraints.py")

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as setup_conn:
        setup_conn.execute(sa.text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                status VARCHAR(20) NOT NULL,
                is_platform_admin BOOLEAN NOT NULL,
                platform_role VARCHAR(20)
            )
        """))
        setup_conn.execute(sa.text("""
            INSERT INTO users (id, email, status, is_platform_admin, platform_role)
            VALUES ('u-legacy', 'legacy@test.com', 'active', 1, NULL)
        """))

    conn = engine.connect()
    # Explicit transaction boundary owned by the test harness
    trans = conn.begin()
    try:
        real_execute = conn.execute
        observed_mutated_role = None

        def intercepted_execute(statement, *args, **kwargs):
            nonlocal observed_mutated_role
            stmt_str = str(statement)
            # Step 5 post-backfill check query
            if "SELECT COUNT(*) FROM users" in stmt_str and "NOT (" in stmt_str:
                # Requirement 3: Assert the real UPDATE changed the row within the transaction before failure is raised
                observed_mutated_role = real_execute(
                    sa.text("SELECT platform_role FROM users WHERE id = 'u-legacy'")
                ).scalar()
                # Requirement 2: Cause post-backfill gate to fail by reporting 1 non-compliant row
                return real_execute(sa.text("SELECT 1"))
            return real_execute(statement, *args, **kwargs)

        monkeypatch.setattr(conn, "execute", intercepted_execute)
        monkeypatch.setattr(m0012.op, "get_bind", lambda: conn)

        with pytest.raises(RuntimeError) as exc_info:
            m0012.upgrade()

        assert "Migration 0012 aborted: Post-backfill check failed" in str(exc_info.value)
        # Verify the row was genuinely mutated to 'admin' before the post-check raised
        assert observed_mutated_role == "admin"

        # Also verify within the still-active transaction before rollback that platform_role remains 'admin'
        in_trans_role = real_execute(
            sa.text("SELECT platform_role FROM users WHERE id = 'u-legacy'")
        ).scalar()
        assert in_trans_role == "admin"

        # Requirement 4: Explicitly roll back the owning transaction using the same connection boundary
        trans.rollback()

        # Requirement 5 & 6: Verify platform_role is back to NULL after rollback on the open connection
        post_rollback_role = conn.execute(
            sa.text("SELECT platform_role FROM users WHERE id = 'u-legacy'")
        ).scalar()
        assert post_rollback_role is None
    finally:
        conn.close()
        engine.dispose()
