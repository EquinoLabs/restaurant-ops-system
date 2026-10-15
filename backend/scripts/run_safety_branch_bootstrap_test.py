import sys
import os
import argparse
import secrets
from typing import Dict, Any, List, Optional, Tuple

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Expected safety branch invariants
NEON_EXPECTED_DATABASE = "neondb"
NEON_EXPECTED_PROJECT_ID = "steep-hall-47922907"
NEON_EXPECTED_BRANCH_ID = "br-weathered-cherry-b34085w9"
NEON_FORBIDDEN_SOURCE_BRANCH_ID = "br-fancy-scene-b38p0d9u"
NEON_EXPECTED_ENDPOINT_ID = "ep-lucky-band-b3tbsmfz"
EXPECTED_MIGRATION_HEAD = "0014_add_missing_tenant_indexes"

EXPECTED_PREEXISTING_USERS = {
    "admin@himachalhospitality.com": {"status": "active", "platform_role": "admin", "is_platform_admin": True},
    "manager@riverside.com": {"status": "active", "platform_role": None, "is_platform_admin": False},
    "manager@town.com": {"status": "active", "platform_role": None, "is_platform_admin": False},
    "waiter@riverside.com": {"status": "active", "platform_role": None, "is_platform_admin": False},
}


def configure_safety_branch_target() -> str:
    """
    In-memory exact-host replacement from repository root .env.
    Translates pooled host to direct endpoint ep-lucky-band-b3tbsmfz without modifying disk files.
    """
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not os.path.exists(env_path):
        raise RuntimeError(f"Root .env not found at {env_path}")

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    db_url = None
    for line in lines:
        if line.strip().startswith("DATABASE_URL="):
            raw_val = line.split("=", 1)[1].strip().strip('"').strip("'")
            db_url = raw_val.replace(
                "ep-sparkling-hat-b304z2wa-pooler.c-4.ap-southeast-1.aws.neon.tech",
                "ep-lucky-band-b3tbsmfz.c-4.ap-southeast-1.aws.neon.tech",
            )
            break

    if not db_url:
        raise RuntimeError("DATABASE_URL not found in .env")

    os.environ["DATABASE_URL"] = db_url

    # Update app settings if already imported
    try:
        from app.core.config import settings
        settings.DATABASE_URL = db_url
    except Exception:
        pass

    return db_url


# Model registrations required for SQLAlchemy metadata
import app.modules.businesses.models  # noqa: F401
import app.modules.outlets.models     # noqa: F401
import app.modules.menus.models       # noqa: F401
import app.modules.staff.models       # noqa: F401
import app.modules.audit.models       # noqa: F401
import app.modules.tables.models      # noqa: F401
import app.modules.orders.models      # noqa: F401

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.security import hash_password, verify_password
from scripts.provision_initial_user import (
    provision_initial_user,
    verify_provisioning_target_connection,
    validate_provisioning_database_target,
    AUTHORIZED_PROVISIONING_EMAIL,
)


def check_preexisting_target_account(session: Session) -> Optional[Dict[str, Any]]:
    """
    Inspects whether the authorized target account already exists.
    Returns account details dictionary if found, None otherwise.
    """
    user = session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    if not user:
        return None
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "platform_role": user.platform_role,
        "is_platform_admin": user.is_platform_admin,
        "created_at": str(getattr(user, "created_at", None)),
        "updated_at": str(getattr(user, "updated_at", None)),
    }


def format_preexisting_account_report(info: Dict[str, Any]) -> str:
    """
    Formats detailed state report when target account already exists.
    Enforces non-mutation refusal invariant.
    """
    lines = [
        "=" * 60,
        "[PREFLIGHT REFUSAL] Pre-existing target account detected!",
        "=" * 60,
        f"  Target Email:       {info['email']}",
        f"  Account UUID:       {info['id']}",
        f"  Display Name:       {info['display_name']}",
        f"  Status:             {info['status']}",
        f"  Platform Role:      {info['platform_role']}",
        f"  Is Platform Admin:  {info['is_platform_admin']}",
        f"  Created At:         {info.get('created_at', 'N/A')}",
        f"  Updated At:         {info.get('updated_at', 'N/A')}",
        "-" * 60,
        "Safety invariant enforced: The smoke test will NOT delete, overwrite, or mutate this account.",
        "Halting execution to prevent destructive modification.",
        "=" * 60,
    ]
    return "\n".join(lines)


def teardown_test_records(
    session: Session,
    user_id: Any,
    audit_id: Any,
) -> Dict[str, Any]:
    """
    Explicit teardown strictly restricted to records demonstrably created by this test run.
    Guarantees:
    - user_id and audit_id must be non-None and explicitly provided.
    - Matches User strictly by (id == user_id AND email == AUTHORIZED_PROVISIONING_EMAIL).
    - Matches AuditLog strictly by (id == audit_id AND entity_id == user_id AND action == 'platform.user.provision').
    - NEVER performs broad DELETE queries or email-only deletions.
    - Verifies all 4 canonical pre-existing users and Active Owner count (0) remain intact.
    """
    if user_id is None or audit_id is None:
        raise ValueError("Teardown refusal: created user_id and audit_id must both be non-None.")

    # 1. Locate specific audit log by exact ID and entity link
    audit_record = (
        session.query(AuditLog)
        .filter(
            AuditLog.id == audit_id,
            AuditLog.entity_id == user_id,
            AuditLog.action == "platform.user.provision",
        )
        .first()
    )
    if not audit_record:
        raise RuntimeError(
            f"Teardown failure: Audit record with ID '{audit_id}' linked to entity '{user_id}' was not found."
        )

    # 2. Locate specific user by exact ID and authorized email
    user_record = (
        session.query(User)
        .filter(
            User.id == user_id,
            User.email == AUTHORIZED_PROVISIONING_EMAIL,
        )
        .first()
    )
    if not user_record:
        raise RuntimeError(
            f"Teardown failure: User record with ID '{user_id}' and email '{AUTHORIZED_PROVISIONING_EMAIL}' was not found."
        )

    # 3. Execute atomic deletion: audit log first, then user
    session.delete(audit_record)
    session.delete(user_record)
    session.commit()

    # 4. Verify post-teardown invariants
    user_check = session.query(User).filter(User.id == user_id).first()
    if user_check is not None:
        raise RuntimeError(f"Teardown verification failed: User '{user_id}' still exists after deletion.")

    audit_check = session.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if audit_check is not None:
        raise RuntimeError(f"Teardown verification failed: Audit record '{audit_id}' still exists after deletion.")

    # Invariant: Active platform owner count remains 0
    active_owners = session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    if active_owners != 0:
        raise RuntimeError(
            f"Invariant violation after teardown: Active Platform Owner count is {active_owners}, expected 0."
        )

    # Invariant: Pre-existing users remain intact
    post_users = {u.email: u for u in session.query(User).all()}
    for email, expected in EXPECTED_PREEXISTING_USERS.items():
        if email not in post_users:
            raise RuntimeError(f"Pre-existing user '{email}' missing after teardown.")
        actual = post_users[email]
        if (
            actual.status != expected["status"]
            or actual.platform_role != expected["platform_role"]
            or actual.is_platform_admin != expected["is_platform_admin"]
        ):
            raise RuntimeError(f"Pre-existing user '{email}' corrupted during teardown.")

    return {
        "status": "success",
        "deleted_user_id": str(user_id),
        "deleted_audit_id": str(audit_id),
    }


def run_c1_bootstrap_test(
    target_env: str = "staging",
    teardown: bool = False,
    session_factory=None,
) -> Dict[str, Any]:
    """
    Executes the automated C1 Initial Account Provisioning smoke test on the authorized target.
    Invariants enforced:
    - Pre-connection target validation and in-connection Neon identity checks.
    - Pre-existing target account check fails closed and outputs diagnostic report without mutating data.
    - Dynamic in-memory password generated via secrets.token_urlsafe(32).
    - Positive authentication check and negative rejection check using verify_password.
    - Exact UUID tracking for user and audit log.
    - Explicit teardown strictly bounded by exact UUIDs when teardown=True.
    """
    print("=" * 60)
    print("ROMS OP-04 — SAFETY BRANCH AUTOMATED C1 BOOTSTRAP TEST")
    print("=" * 60)

    if session_factory is None:
        if "DATABASE_URL" not in os.environ or NEON_EXPECTED_ENDPOINT_ID not in os.environ.get("DATABASE_URL", ""):
            configure_safety_branch_target()
        from app.db.session import SessionLocal
        session_factory = SessionLocal

    # 1. Pre-Connection Target Verification Gate
    target_info = validate_provisioning_database_target(target_env=target_env)
    print(f"Target Env:      {target_info['target_env']}")
    print(f"Target Host:     {target_info['host']}:{target_info['port']}")
    print(f"Target Database: {target_info['database']}")
    print(f"Masked URI:      {target_info['masked_uri']}")
    print("-" * 60)

    # 2. Live In-Connection Preflight Checks
    pre_session = session_factory()
    try:
        verify_provisioning_target_connection(pre_session.connection(), target_env=target_env)
        print("[PREFLIGHT] Live target identity and schema checks PASSED.")

        # Check pre-existing users
        pre_users = pre_session.query(User).all()
        user_emails = {u.email: u for u in pre_users}
        for email, expected in EXPECTED_PREEXISTING_USERS.items():
            if email not in user_emails:
                raise RuntimeError(f"Missing expected pre-existing user '{email}'.")
            actual = user_emails[email]
            if (
                actual.status != expected["status"]
                or actual.platform_role != expected["platform_role"]
                or actual.is_platform_admin != expected["is_platform_admin"]
            ):
                raise RuntimeError(
                    f"Pre-existing user '{email}' mismatch: status={actual.status}, role={actual.platform_role}, is_admin={actual.is_platform_admin}"
                )

        print(f"[PREFLIGHT] Verified {len(EXPECTED_PREEXISTING_USERS)} pre-existing users intact.")

        # Invariant check: Active owners before execution must be 0
        active_owners_before = pre_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
        if active_owners_before != 0:
            raise RuntimeError(f"Invariant violation before execution: Active Platform Owner count is {active_owners_before}, expected 0.")
        print(f"[PREFLIGHT] Active Platform Owners before execution: {active_owners_before} (PASS)")

        # Target account existence check (fails closed, reports state, does not overwrite)
        existing_info = check_preexisting_target_account(pre_session)
        if existing_info is not None:
            report_text = format_preexisting_account_report(existing_info)
            print(report_text, file=sys.stderr)
            raise RuntimeError(
                f"Target account '{AUTHORIZED_PROVISIONING_EMAIL}' already exists (UUID: {existing_info['id']}). "
                f"Smoke test halted to protect existing account state."
            )
        print(f"[PREFLIGHT] Target account '{AUTHORIZED_PROVISIONING_EMAIL}': NOT FOUND (PASS)")

    finally:
        pre_session.close()

    print("-" * 60)
    print(f"Executing C1 Base User Provisioning for '{AUTHORIZED_PROVISIONING_EMAIL}'...")

    # 3. Dynamic in-memory credential generation per run
    test_password = secrets.token_urlsafe(32)
    test_pw_hash = hash_password(test_password)

    write_session = session_factory()
    created_user_id = None
    created_audit_id = None
    try:
        verify_provisioning_target_connection(write_session.connection(), target_env=target_env)
        success = provision_initial_user(
            email=AUTHORIZED_PROVISIONING_EMAIL,
            password_hash=test_pw_hash,
            display_name="Platform Owner",
            confirm=True,
            target_env=target_env,
            operator="automated_test_runner@roms.com",
            db=write_session,
        )
        if not success:
            raise RuntimeError("provision_initial_user returned False. Execution failed.")
        write_session.commit()
    except Exception:
        write_session.rollback()
        raise
    finally:
        write_session.close()

    print("[SUCCESS] provision_initial_user completed successfully.")
    print("-" * 60)
    print("Running Post-Execution Read-Only Verifications...")

    # 4. Post-Execution Verification
    post_session = session_factory()
    try:
        verify_provisioning_target_connection(post_session.connection(), target_env=target_env)

        # 1. Target account exists exactly once
        target_users = post_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).all()
        if len(target_users) != 1:
            raise RuntimeError(f"Post-execution error: Target account count is {len(target_users)}, expected 1.")
        created_user = target_users[0]
        created_user_id = created_user.id
        print(f"1. Target account exists:   YES (UUID: {created_user_id})")

        # 2. Status is active
        if created_user.status != "active":
            raise RuntimeError(f"Post-execution error: status is '{created_user.status}', expected 'active'.")
        print(f"2. Status is active:        YES ({created_user.status})")

        # 3. platform_role is NULL
        if created_user.platform_role is not None:
            raise RuntimeError(f"Post-execution error: platform_role is '{created_user.platform_role}', expected NULL.")
        print(f"3. Platform role is NULL:   YES ({created_user.platform_role})")

        # 4. is_platform_admin is false
        if created_user.is_platform_admin is not False:
            raise RuntimeError(f"Post-execution error: is_platform_admin is '{created_user.is_platform_admin}', expected False.")
        print(f"4. Is platform admin false: YES ({created_user.is_platform_admin})")

        # 5. Password Authentication Verification (Positive Match & Negative Rejection)
        if not verify_password(test_password, created_user.password_hash):
            raise RuntimeError("Post-execution error: Generated password failed to authenticate against stored password_hash.")
        wrong_password_attempt = "WrongPass_" + secrets.token_urlsafe(16)
        if verify_password(wrong_password_attempt, created_user.password_hash):
            raise RuntimeError("Post-execution error: Incorrect password unexpectedly authenticated against stored hash.")
        print("5. Password Authentication: PASSED (Positive Match & Negative Rejection)")

        # Discard password reference in memory (note: Python GC unbinding, no low-level memory zeroing guarantees)
        del test_password

        # 6. Active Owner count remains zero
        active_owners_after = post_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
        if active_owners_after != 0:
            raise RuntimeError(f"Invariant violation: Active Platform Owner count is {active_owners_after}, expected 0.")
        print(f"6. Active Owner count:      {active_owners_after} (Invariant Maintained)")

        # 7. Audit event exists and corresponds to this operation
        audit_event = (
            post_session.query(AuditLog)
            .filter(AuditLog.action == "platform.user.provision", AuditLog.entity_id == created_user_id)
            .first()
        )
        if not audit_event:
            raise RuntimeError(f"Audit log 'platform.user.provision' not found for created user {created_user_id}.")
        created_audit_id = audit_event.id
        meta = audit_event.metadata_json or {}
        if meta.get("target_email") != AUTHORIZED_PROVISIONING_EMAIL or meta.get("action_type") != "platform.user.provision":
            raise RuntimeError(f"Audit log metadata mismatch: {meta}")
        print(f"7. Audit event verified:    YES (Audit ID: {created_audit_id}, Action: {audit_event.action})")

        # 8. Alembic revision remains 0014_add_missing_tenant_indexes
        rev = post_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if rev != EXPECTED_MIGRATION_HEAD:
            raise RuntimeError(f"Alembic revision mismatch: found '{rev}', expected '{EXPECTED_MIGRATION_HEAD}'.")
        print(f"8. Alembic revision:        {rev} (Unchanged)")

        # 9. Four pre-existing users remain intact
        post_users = {u.email: u for u in post_session.query(User).all()}
        for email, expected in EXPECTED_PREEXISTING_USERS.items():
            if email not in post_users:
                raise RuntimeError(f"Pre-existing user '{email}' missing after C1.")
            actual = post_users[email]
            if (
                actual.status != expected["status"]
                or actual.platform_role != expected["platform_role"]
                or actual.is_platform_admin != expected["is_platform_admin"]
            ):
                raise RuntimeError(
                    f"Pre-existing user '{email}' altered during C1: status={actual.status}, role={actual.platform_role}, is_admin={actual.is_platform_admin}"
                )
        print(f"9. Pre-existing users:      4/4 Verified Intact")

    finally:
        post_session.close()

    print("=" * 60)
    print("ALL C1 POST-EXECUTION VERIFICATIONS PASSED SUCCESSFULLY.")
    print("=" * 60)

    # 5. Teardown (if requested)
    teardown_result = None
    if teardown:
        print(f"Executing explicit exact-ID teardown for User '{created_user_id}' and Audit '{created_audit_id}'...")
        cleanup_session = session_factory()
        try:
            teardown_result = teardown_test_records(
                session=cleanup_session,
                user_id=created_user_id,
                audit_id=created_audit_id,
            )
            print(f"[TEARDOWN SUCCESS] User '{created_user_id}' and Audit '{created_audit_id}' cleanly deleted.")
        finally:
            cleanup_session.close()
    else:
        print(
            f"[INFO] Teardown was not requested. Created records preserved: User ID '{created_user_id}', Audit ID '{created_audit_id}'."
        )

    return {
        "status": "success",
        "created_user_id": str(created_user_id),
        "created_audit_id": str(created_audit_id),
        "auth_verified": True,
        "teardown_performed": teardown,
        "teardown_result": teardown_result,
    }


def main():
    parser = argparse.ArgumentParser(
        description="ROMS OP-04: Automated C1 Initial User Provisioning Smoke Test on Neon Safety Branch"
    )
    parser.add_argument(
        "--target-env",
        choices=["staging", "production", "test"],
        default="staging",
        help="Target environment (must be 'staging' for safety branch; default: staging)",
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Execute exact-ID teardown of test-created records after verification passes",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only run preflight target and account checks without creating records",
    )

    args = parser.parse_args()

    # Configure safety branch target URL in process memory
    configure_safety_branch_target()

    if args.check_only:
        print("[CHECK-ONLY] Running preflight inspections...")
        from app.db.session import SessionLocal
        target_info = validate_provisioning_database_target(target_env=args.target_env)
        print(f"Target: {target_info['host']} ({target_info['target_env']})")
        session = SessionLocal()
        try:
            verify_provisioning_target_connection(session.connection(), target_env=args.target_env)
            existing = check_preexisting_target_account(session)
            if existing:
                print(format_preexisting_account_report(existing))
            else:
                print(f"[OK] Target account '{AUTHORIZED_PROVISIONING_EMAIL}' does not exist.")
        finally:
            session.close()
        sys.exit(0)

    try:
        run_c1_bootstrap_test(target_env=args.target_env, teardown=args.teardown)
    except Exception as e:
        print(f"[ERROR] Smoke test failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
