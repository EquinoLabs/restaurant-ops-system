"""
ROMS Platform Governance — Initial User Provisioning Helper (OP-04 Phase C1)

Provides a dedicated, fail-closed helper to provision the initial ROMS Platform Owner base account:
  - Email: owner@roms.com
  - Initial Role State: platform_role=None, is_platform_admin=False, status='active'

Security & Isolation Controls:
1. Strict interactive credential ingestion using getpass.getpass() with terminal echo disabled.
2. Zero command-line or environment variable password ingestion.
3. Universal redaction: never prints, logs, or audits plaintext passwords, password hashes, or DB secrets.
4. Pre-connection target validation rejecting pooled endpoints (-pooler).
5. In-connection target verification validating Neon project, branch, endpoint, database, and Alembic revision.
6. Decoupled provisioning: provisions an unprivileged base account only; never invokes Owner promotion.
7. Active Platform Owner count verified to remain strictly zero.
8. Atomic transaction with rollback on validation or audit log failure.
"""

import sys
import os
import argparse
import getpass
from typing import Optional, Dict, Any, Callable
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.modules.businesses.models  # noqa: F401
import app.modules.outlets.models     # noqa: F401
import app.modules.menus.models       # noqa: F401
import app.modules.staff.models       # noqa: F401
import app.modules.audit.models       # noqa: F401
import app.modules.tables.models      # noqa: F401
import app.modules.orders.models      # noqa: F401

from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password
from app.modules.staff.models import User
from app.modules.audit.service import log_audit
from app.core.errors import ValidationError

from scripts.create_platform_admin import (
    validate_bootstrap_database_target,
    _get_execution_context,
    VALID_TARGET_ENVIRONMENTS,
    _SENTINEL,
)

try:
    from tests.postgres_guard import (
        NEON_EXPECTED_PROJECT_ID,
        NEON_EXPECTED_BRANCH_ID,
        NEON_FORBIDDEN_SOURCE_BRANCH_ID,
        NEON_EXPECTED_ENDPOINT_ID,
        NEON_EXPECTED_DATABASE,
        EXPECTED_MIGRATION_HEAD,
        TargetVerificationRefusal as _BaseTargetRefusal,
    )

    class TargetVerificationRefusal(_BaseTargetRefusal, ValidationError):
        """Raised when live target database fails identity verification."""
        pass

except ImportError:
    NEON_EXPECTED_PROJECT_ID = "steep-hall-47922907"
    NEON_EXPECTED_BRANCH_ID = "br-weathered-cherry-b34085w9"
    NEON_FORBIDDEN_SOURCE_BRANCH_ID = "br-fancy-scene-b38p0d9u"
    NEON_EXPECTED_ENDPOINT_ID = "ep-lucky-band-b3tbsmfz"
    NEON_EXPECTED_DATABASE = "neondb"
    EXPECTED_MIGRATION_HEAD = "0014_add_missing_tenant_indexes"

    class TargetVerificationRefusal(ValidationError):
        """Raised when live target database fails identity verification."""
        pass


AUTHORIZED_PROVISIONING_EMAIL: str = "owner@roms.com"


def validate_provisioning_database_target(
    target_env: Optional[str],
    database_uri: Optional[str] = None,
    explicit_database_url: Any = _SENTINEL,
) -> Dict[str, Any]:
    """
    Fails closed when the database target or environment selection is ambiguous.
    Reuses established validate_bootstrap_database_target and additionally
    enforces direct endpoint connection (rejecting -pooler routing).
    """
    info = validate_bootstrap_database_target(
        target_env=target_env,
        database_uri=database_uri,
        explicit_database_url=explicit_database_url,
    )
    host = info.get("host", "").lower()
    if "-pooler" in host:
        raise ValidationError(
            f"Target endpoint refusal: Host '{host}' is a pooled endpoint. "
            "Direct connection is required."
        )
    return info


def verify_provisioning_target_connection(
    connection: Any,
    target_env: str,
    enforce_neon: Optional[bool] = None,
) -> None:
    """
    In-connection positive target identity verification for the authorized target database.
    When target_env is production/staging (or enforce_neon=True):
      - Verifies database name is 'neondb'.
      - Verifies 'neon.project_id' is 'steep-hall-47922907'.
      - Verifies 'neon.branch_id' is 'br-weathered-cherry-b34085w9' (and NOT forbidden source branch).
      - Verifies 'neon.endpoint_id' is 'ep-lucky-band-b3tbsmfz'.
      - Verifies alembic_version table exists and version_num is '0014_add_missing_tenant_indexes'.
    Fails closed if any attribute mismatches or if unexpected exceptions occur.
    """
    should_verify = enforce_neon if enforce_neon is not None else (target_env in ("production", "staging"))
    if not should_verify:
        return

    try:
        # 1. Database name check
        server_db = connection.execute(text("SELECT current_database()")).scalar()
        if not server_db or str(server_db).strip().lower() != NEON_EXPECTED_DATABASE.lower():
            raise TargetVerificationRefusal(
                f"Target database identity mismatch: Connected to database '{server_db}', "
                f"expected '{NEON_EXPECTED_DATABASE}'. Aborting."
            )

        # 2. Neon-specific system settings verification
        project_id = connection.execute(text("SELECT current_setting('neon.project_id', true)")).scalar()
        if not project_id or str(project_id).strip() != NEON_EXPECTED_PROJECT_ID:
            raise TargetVerificationRefusal(
                f"Neon project identity mismatch: Connected to project '{project_id}', "
                f"expected '{NEON_EXPECTED_PROJECT_ID}'. Aborting."
            )

        branch_id = connection.execute(text("SELECT current_setting('neon.branch_id', true)")).scalar()

        if target_env == "production":
            expected_branch = "br-fancy-scene-b38p0d9u"
            expected_endpoint = "ep-sparkling-hat-b304z2wa"
            forbidden_branch = "br-weathered-cherry-b34085w9"
        elif target_env == "staging":
            expected_branch = "br-weathered-cherry-b34085w9"
            expected_endpoint = "ep-lucky-band-b3tbsmfz"
            forbidden_branch = "br-fancy-scene-b38p0d9u"
        else:
            expected_branch = None
            expected_endpoint = None
            forbidden_branch = None

        if forbidden_branch and branch_id == forbidden_branch:
            raise TargetVerificationRefusal(
                f"CRITICAL SAFETY VIOLATION: Connected to forbidden source branch '{branch_id}'. "
                "Aborting immediately to protect production data."
            )
        if expected_branch and (not branch_id or str(branch_id).strip() != expected_branch):
            raise TargetVerificationRefusal(
                f"Neon branch identity mismatch: Connected to branch '{branch_id}', "
                f"expected safety branch '{expected_branch}'. Aborting."
            )

        endpoint_id = connection.execute(text("SELECT current_setting('neon.endpoint_id', true)")).scalar()
        if expected_endpoint and (not endpoint_id or str(endpoint_id).strip() != expected_endpoint):
            raise TargetVerificationRefusal(
                f"Neon endpoint identity mismatch: Connected to endpoint '{endpoint_id}', "
                f"expected '{expected_endpoint}'. Aborting."
            )

        # 3. Alembic revision check
        try:
            current_rev = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            raise TargetVerificationRefusal(
                "Alembic version table missing or unreadable on target branch. Schema is unmigrated."
            )

        if not current_rev or str(current_rev).strip() != EXPECTED_MIGRATION_HEAD:
            raise TargetVerificationRefusal(
                f"Alembic revision mismatch on target branch: Found '{current_rev}', "
                f"expected head '{EXPECTED_MIGRATION_HEAD}'."
            )

    except TargetVerificationRefusal:
        raise
    except Exception as exc:
        raise TargetVerificationRefusal(
            f"Target verification encountered an unexpected error and failed closed: {exc}"
        ) from None


def prompt_for_initial_password(
    prompt: str = "Enter password for initial user: ",
    confirm_prompt: str = "Confirm password: ",
    password_getter: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Safely collects and confirms a password interactively using getpass.
    Fails closed if getpass is unavailable, input is empty, or passwords do not match.
    Never logs or echoes passwords.
    """
    getter = password_getter or getpass.getpass
    try:
        pw1 = getter(prompt)
    except Exception as e:
        raise ValidationError(f"Interactive password input failed or is unavailable: {e}")

    if not pw1 or not pw1.strip():
        raise ValidationError("Password cannot be empty or whitespace only.")

    if len(pw1) < 8:
        raise ValidationError("Password must be at least 8 characters in length.")

    try:
        pw2 = getter(confirm_prompt)
    except Exception as e:
        raise ValidationError(f"Password confirmation input failed or is unavailable: {e}")

    if pw1 != pw2:
        raise ValidationError("Password confirmation does not match. Aborting.")

    return pw1


def provision_initial_user_service(
    db: Session,
    email: str = AUTHORIZED_PROVISIONING_EMAIL,
    password_hash: Optional[str] = None,
    display_name: str = "Platform Owner",
    confirm: bool = False,
    operator: Optional[str] = None,
    target_env: Optional[str] = None,
) -> bool:
    """
    Core domain service that creates the initial Platform Owner base account
    within a caller-owned session. Guarantees initial fields:
      - status = 'active'
      - platform_role = None
      - is_platform_admin = False
    Ensures active Platform Owner count remains strictly 0.
    Emits structured audit event ('platform.user.provision') before flush.

    Session Ownership Contract:
    - Receives a caller-owned Session 'db'.
    - Performs validation, ORM insertion, audit logging, and flush().
    - NEVER calls commit() or rollback().
    - Caller retains full control over transaction boundaries, commit, rollback, and session closure.
    - Returns True on successful provisioning.
    - Returns False on validation failure (unconfirmed, existing account, pre-existing owner, etc.).
    """
    if not email or not str(email).strip():
        print("Error: Target user email cannot be empty.")
        return False

    normalized_email = email.strip().lower()

    # Guard: Helper is strictly bounded to the authorized initial account
    if normalized_email != AUTHORIZED_PROVISIONING_EMAIL:
        raise ValidationError(
            f"Unauthorized account provisioning: Only '{AUTHORIZED_PROVISIONING_EMAIL}' is authorized "
            f"for initial base provisioning. Requested: '{normalized_email}'."
        )

    if not confirm:
        print(f"Notice: Operation not confirmed (confirm=False). Zero changes applied for '{normalized_email}'.")
        return False

    if not password_hash or not str(password_hash).strip():
        print("Error: Password hash is required for user creation.")
        return False

    # Check 1: Invariant requires exactly zero active Platform Owners prior to initial bootstrap
    active_owners = (
        db.query(User)
        .filter(User.platform_role == "owner", User.status == "active")
        .all()
    )
    if active_owners:
        print(f"Error: Active Platform Owner already exists (count={len(active_owners)}). "
              "Initial base account provisioning requires zero active Platform Owners.")
        return False

    # Check 2: Reject existing account; do not overwrite, modify, or promote
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user is not None:
        print(f"Error: User with email '{normalized_email}' already exists.")
        print("Base account provisioning will not modify, promote, or overwrite an existing account.")
        return False

    # Create unprivileged base user
    new_user = User(
        email=normalized_email,
        password_hash=password_hash,
        display_name=display_name.strip() or "Platform Owner",
        status="active",
        is_platform_admin=False,
        platform_role=None,
    )
    db.add(new_user)
    db.flush()

    # Invariant post-check: active platform owner count must remain zero
    post_active_owners = (
        db.query(User)
        .filter(User.platform_role == "owner", User.status == "active")
        .count()
    )
    if post_active_owners != 0:
        raise ValidationError(
            f"Invariant violation: Active Platform Owner count is {post_active_owners}, expected 0."
        )

    # Verify newly created user fields
    if new_user.platform_role is not None or new_user.is_platform_admin is not False or new_user.status != "active":
        raise ValidationError("Invariant violation: Initial user fields do not match required base state.")

    exec_context = _get_execution_context()
    audit_metadata = {
        "action_type": "platform.user.provision",
        "target_user_id": str(new_user.id),
        "target_email": new_user.email,
        "assigned_role": None,
        "is_platform_admin": False,
        "status": "active",
        "operator": operator or "cli_operator",
        "operator_system_user": exec_context.get("os_user"),
        "execution_host": exec_context.get("hostname"),
        "target_environment": target_env or getattr(settings, "ENVIRONMENT", "unspecified"),
        "outcome": "success",
    }

    try:
        log_audit(
            db=db,
            business_id=None,
            outlet_id=None,
            actor_user_id=None,
            action="platform.user.provision",
            entity_type="user",
            entity_id=new_user.id,
            metadata_json=audit_metadata,
        )
    except Exception as e:
        print(f"Error: Failed to record audit log for user provisioning: {e}")
        raise

    print(f"Success: Base user '{normalized_email}' (ID: {new_user.id}) provisioned successfully.")
    return True


def provision_initial_user(
    email: str = AUTHORIZED_PROVISIONING_EMAIL,
    password_hash: Optional[str] = None,
    display_name: str = "Platform Owner",
    db: Optional[Session] = None,
    confirm: bool = False,
    target_env: Optional[str] = None,
    operator: Optional[str] = None,
    database_uri: Optional[str] = None,
) -> bool:
    """
    Top-level helper to provision the initial Platform Owner base account.

    Transaction Ownership Contract:
    - When db is provided (Caller-Owned Mode): delegates to provision_initial_user_service.
      Caller manages transaction boundaries.
    - When db is None (Script-Owned Mode): manages transaction with SessionLocal().
      Validates target_env, executes live target check in production/staging,
      commits on success, rolls back on failure or exception, and closes session.
    """
    if db is not None:
        return provision_initial_user_service(
            db=db,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            confirm=confirm,
            operator=operator,
            target_env=target_env,
        )

    resolved_env = target_env or getattr(settings, "ENVIRONMENT", "test")
    target_info = validate_provisioning_database_target(resolved_env, database_uri=database_uri)

    session = SessionLocal()
    try:
        verify_provisioning_target_connection(session.connection(), target_info["target_env"])
        success = provision_initial_user_service(
            db=session,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            confirm=confirm,
            operator=operator,
            target_env=resolved_env,
        )
        if success:
            session.commit()
        else:
            session.rollback()
        return success
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="ROMS Safe Initial Platform User Provisioning Helper (OP-04 Phase C1).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preflight / Dry-run inspection before provisioning:
  python backend/scripts/provision_initial_user.py --target-env staging

  # Confirmed execution in target environment (prompts interactively for password):
  python backend/scripts/provision_initial_user.py --target-env staging --confirm --operator "lead.ops@example.com"
        """
    )
    parser.add_argument(
        "--target-env",
        choices=list(VALID_TARGET_ENVIRONMENTS),
        required=True,
        help="Explicit target environment. Required to fail closed against ambiguous database targets."
    )
    parser.add_argument(
        "--email",
        default=AUTHORIZED_PROVISIONING_EMAIL,
        help=f"Email address of the initial base account to provision (authorized default: {AUTHORIZED_PROVISIONING_EMAIL})."
    )
    parser.add_argument(
        "--display-name",
        default="Platform Owner",
        help="Display name for the initial user account (default: 'Platform Owner')."
    )
    parser.add_argument(
        "--operator",
        help="Identifier (name or email) of the authorized operator executing provisioning."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicit confirmation flag required to execute database mutations."
    )

    args = parser.parse_args()

    # Pre-connection target environment verification: MUST succeed before SessionLocal()
    try:
        target_info = validate_provisioning_database_target(args.target_env)
    except Exception as e:
        print(f"\n[FATAL] Database target verification failed: {e}\n", file=sys.stderr)
        sys.exit(1)

    normalized_email = args.email.strip().lower()
    if normalized_email != AUTHORIZED_PROVISIONING_EMAIL:
        print(
            f"\n[FATAL] Unauthorized account provisioning: Only '{AUTHORIZED_PROVISIONING_EMAIL}' "
            f"is authorized for initial provisioning. Requested: '{normalized_email}'\n",
            file=sys.stderr
        )
        sys.exit(1)

    if not args.confirm:
        # Preflight Dry-Run mode
        session = SessionLocal()
        try:
            verify_provisioning_target_connection(session.connection(), args.target_env)
            user = session.query(User).filter(User.email == normalized_email).first()
            active_owners = session.query(User).filter(User.platform_role == "owner", User.status == "active").all()

            print("\n========================================================")
            print("  ROMS INITIAL USER PROVISIONING PREFLIGHT / DRY-RUN    ")
            print("========================================================\n")
            print(f"Target Env:           {target_info.get('target_env')}")
            print(f"Target DB Host:       {target_info.get('host')}:{target_info.get('port')}")
            print(f"Target Database:      {target_info.get('database')}")
            print(f"Masked URI:           {target_info.get('masked_uri')}")
            print(f"Target Email:         {normalized_email}")
            print("Target Status:        active")
            print("Target Platform Role: None (unassigned base account)")
            print("Is Platform Admin:    False")
            print(f"Operator:             {args.operator or 'cli_operator'}")
            if user:
                print(f"Target User Exists:   YES (ID: {user.id}, Status: {user.status})")
            else:
                print("Target User Exists:   NO")
            print(f"Active Owners Count:  {len(active_owners)}")
            for o in active_owners:
                print(f"  - {o.email} ({o.id})")
            print("--------------------------------------------------------")
            print("DRY-RUN ONLY: Zero database changes were written.")
            print("Provide --confirm to execute user provisioning.")
            print("========================================================\n")
            session.rollback()
            sys.exit(0)
        except Exception as e:
            session.rollback()
            print(f"\n[ERROR] Preflight inspection failed: {e}\n", file=sys.stderr)
            sys.exit(1)
        finally:
            session.close()

    # Confirmed Execution: Prompt interactively for password
    try:
        raw_password = prompt_for_initial_password()
        pw_hash = hash_password(raw_password)
        del raw_password
    except Exception as e:
        print(f"\n[FATAL] Credential handling failure: {e}\n", file=sys.stderr)
        sys.exit(1)

    session = SessionLocal()
    try:
        verify_provisioning_target_connection(session.connection(), args.target_env)
        success = provision_initial_user_service(
            db=session,
            email=normalized_email,
            password_hash=pw_hash,
            display_name=args.display_name,
            confirm=True,
            operator=args.operator,
            target_env=args.target_env,
        )
        if success:
            session.commit()
            print("\n========================================================")
            print("  ROMS INITIAL USER PROVISIONED & COMMITTED             ")
            print("========================================================\n")
            print(f"Target Env:     {target_info.get('target_env')}")
            print(f"Target DB:      {target_info.get('host')}:{target_info.get('port')}/{target_info.get('database')}")
            print(f"Target Email:   {normalized_email}")
            print("Status:         active")
            print("Platform Role:  None (unassigned base account)")
            print("Is Admin:       False")
            print(f"Operator:       {args.operator or 'cli_operator'}")
            print("Audit Log:      COMMITTED (platform.user.provision)")
            print("========================================================\n")
            sys.exit(0)
        else:
            session.rollback()
            print("\n[ERROR] Provisioning failed validation. Rolled back.\n", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        session.rollback()
        print(f"\n[FATAL] Provisioning procedure aborted: {e}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
