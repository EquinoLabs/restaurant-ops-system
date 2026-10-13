import sys
import os
import argparse
import getpass
import socket
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, Any, List

# Ensure backend root is on sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.modules.businesses.models  # noqa: F401
import app.modules.outlets.models     # noqa: F401
import app.modules.menus.models       # noqa: F401
import app.modules.staff.models       # noqa: F401
import app.modules.audit.models       # noqa: F401
import app.modules.tables.models      # noqa: F401
import app.modules.orders.models      # noqa: F401
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.modules.staff.models import User
from app.modules.audit.service import log_audit
from app.modules.businesses.platform_service import _acquire_admin_serialization_lock
from app.core.errors import ValidationError

VALID_TARGET_ENVIRONMENTS = ("production", "staging", "development", "local", "test")
_SENTINEL = object()


def _get_execution_context() -> Dict[str, str]:
    """
    Collects supplementary OS user and host execution context for audit trails.
    Note: These are non-cryptographic environment attributes provided for forensic
    correlation; they do not establish verified identity or replace external authorization.
    """
    try:
        os_user = getpass.getuser()
    except Exception:
        os_user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"

    return {
        "os_user": os_user,
        "hostname": hostname,
    }


def validate_bootstrap_database_target(
    target_env: Optional[str],
    database_uri: Optional[str] = None,
    explicit_database_url: Any = _SENTINEL,
) -> Dict[str, Any]:
    """
    Fails closed when the database target or environment selection is ambiguous.
    Guarantees:
      1. Explicit target environment is required.
      2. In production or staging, implicit fallback to localhost or unconfigured database is prohibited.
      3. In production or staging, loopback/localhost targets are prohibited.
      4. In local/development, pointing to remote cloud databases is prohibited.
      5. Sensitive credentials are fully redacted from output fields.
    """
    if not target_env or not str(target_env).strip():
        raise ValidationError(
            "Target environment (--target-env) is required for platform bootstrap. "
            f"Allowed environments: {list(VALID_TARGET_ENVIRONMENTS)}"
        )

    clean_env = str(target_env).strip().lower()
    if clean_env not in VALID_TARGET_ENVIRONMENTS:
        raise ValidationError(
            f"Invalid target environment '{target_env}'. "
            f"Allowed environments: {list(VALID_TARGET_ENVIRONMENTS)}"
        )

    raw_uri = database_uri if database_uri is not None else settings.SQLALCHEMY_DATABASE_URI
    configured_url = settings.DATABASE_URL if explicit_database_url is _SENTINEL else explicit_database_url
    is_explicit = bool(configured_url and str(configured_url).strip())

    try:
        parsed = urlparse(raw_uri)
    except Exception as e:
        raise ValidationError(f"Failed to parse database connection URI: {e}")

    host = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    db_name = (parsed.path or "").lstrip("/")
    scheme = parsed.scheme.lower()
    is_localhost = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "")

    # Rule 1: Production/Staging require explicitly configured DATABASE_URL
    if clean_env in ("production", "staging"):
        if not is_explicit:
            raise ValidationError(
                f"Target environment '{clean_env}' requires an explicitly configured DATABASE_URL. "
                "Implicit fallback to default localhost settings is prohibited in bootstrap mode."
            )
        if is_localhost:
            raise ValidationError(
                f"Target environment '{clean_env}' cannot target a localhost/loopback database ('{host}'). "
                "An explicit remote database host is required."
            )

    # Rule 2: Local/Development must not target remote cloud databases
    if clean_env in ("local", "development"):
        if is_explicit and not is_localhost and host not in ("testserver", "sqlite"):
            raise ValidationError(
                f"Target environment mismatch: --target-env is '{clean_env}', but DATABASE_URL points to "
                f"remote host '{host}'. If targeting production or staging, specify --target-env accordingly."
            )

    # Build masked URI (redacting credentials)
    if parsed.password:
        masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
        masked_uri = urlunparse((parsed.scheme, masked_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    else:
        masked_uri = raw_uri

    return {
        "target_env": clean_env,
        "host": host or "localhost",
        "port": port,
        "database": db_name or "roms_db",
        "scheme": scheme,
        "masked_uri": masked_uri,
        "is_explicit": is_explicit,
    }


def promote_user_to_platform_admin_service(
    db: Session,
    email: str,
    role: str = "admin",
    confirm: bool = True,
    operator: Optional[str] = None,
    target_env: Optional[str] = None,
) -> bool:
    """
    Core domain service that promotes an existing user account to Platform Administrator
    or designates the first Platform Owner within an existing caller-owned session.
    Dual-writes is_platform_admin=True and platform_role=role atomically under transaction serialization.
    Emits structured audit events ('platform.owner.bootstrap' or 'platform.admin.promote') before flush.

    Session Ownership Contract:
    - Receives a caller-owned Session 'db'.
    - Performs validation, advisory lock acquisition, ORM mutations, audit logging, and flush().
    - NEVER calls commit() or rollback().
    - Caller retains full control over transaction boundaries, commit, rollback, and session closure.
    - Returns True on successful promotion or safe idempotent no-op.
    - Returns False on validation failure (invalid role, user not found, non-active account, second owner attempt, unconfirmed).
    """
    if not email or not str(email).strip():
        print("Error: Target user email cannot be empty.")
        return False

    normalized_email = email.strip().lower()
    if role is None:
        normalized_role = "admin"
    elif isinstance(role, str):
        normalized_role = role.strip().lower()
    else:
        normalized_role = str(role).strip().lower()

    if normalized_role not in ("admin", "owner"):
        print(f"Error: Invalid platform role '{role}'. Allowed roles: 'admin', 'owner'.")
        return False

    if not confirm:
        print(f"Notice: Operation not confirmed (confirm=False). Zero changes applied for '{normalized_email}'.")
        return False

    _acquire_admin_serialization_lock(db)

    # Check for target user and fail closed if missing or ambiguous
    user_query = db.query(User).filter(User.email == normalized_email)
    raw_all = user_query.all()
    if isinstance(raw_all, list):
        if not raw_all:
            print(f"Error: User with email '{normalized_email}' was not found.")
            print("Please create the user account first before promoting to platform administrator.")
            return False
        if len(raw_all) > 1:
            print(f"Error: Ambiguous user identification: {len(raw_all)} accounts found with email '{normalized_email}'.")
            return False
        user = raw_all[0]
    else:
        # Fallback for mock sessions that only mock .first()
        user = user_query.first()
        if not user:
            print(f"Error: User with email '{normalized_email}' was not found.")
            print("Please create the user account first before promoting to platform administrator.")
            return False

    if user.status != "active":
        print(f"Error: User '{normalized_email}' account status is '{user.status}'. Only 'active' accounts can be promoted.")
        return False

    exec_context = _get_execution_context()

    if normalized_role == "owner":
        raw_owners = (
            db.query(User)
            .filter(User.platform_role == "owner", User.status == "active")
            .all()
        )
        active_owners = raw_owners if isinstance(raw_owners, list) else []
        if len(active_owners) > 1:
            print(f"Error: Anomalous platform state: {len(active_owners)} active Platform Owners already exist. Cannot proceed.")
            return False

        if active_owners:
            if any(o.id == user.id for o in active_owners):
                if not user.is_platform_admin:
                    user.is_platform_admin = True
                    db.flush()
                    print(f"Success: Repaired inconsistent platform administrator flag for active Platform Owner '{normalized_email}'.")
                    return True
                print(f"Notice: User '{normalized_email}' is already the active Platform Owner.")
                return True
            print("Error: An active Platform Owner already exists. Cannot designate another Owner.")
            return False

        user.is_platform_admin = True
        user.platform_role = "owner"
        db.flush()

        audit_metadata = {
            "bootstrap_stage": "INITIAL_OWNER_BOOTSTRAP",
            "action_type": "platform.owner.bootstrap",
            "target_user_id": str(user.id),
            "target_email": user.email,
            "assigned_role": "owner",
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
                action="platform.owner.bootstrap",
                entity_type="user",
                entity_id=user.id,
                metadata_json=audit_metadata,
            )
        except Exception as e:
            print(f"Error: Failed to record audit log for owner bootstrap: {e}")
            raise

        print(f"Success: User '{normalized_email}' (ID: {user.id}) has been designated as Platform Owner.")
        return True

    # normalized_role == "admin"
    if user.platform_role == "owner":
        print(f"Notice: User '{normalized_email}' is the Platform Owner and cannot be modified.")
        return True

    if user.is_platform_admin and user.platform_role == "admin":
        print(f"Notice: User '{normalized_email}' is already a Platform Administrator.")
        return True

    user.is_platform_admin = True
    user.platform_role = "admin"
    db.flush()

    audit_metadata = {
        "action_type": "platform.admin.promote",
        "target_user_id": str(user.id),
        "target_email": user.email,
        "assigned_role": "admin",
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
            action="platform.admin.promote",
            entity_type="user",
            entity_id=user.id,
            metadata_json=audit_metadata,
        )
    except Exception as e:
        print(f"Error: Failed to record audit log for admin promotion: {e}")
        raise

    print(f"Success: User '{normalized_email}' (ID: {user.id}) has been promoted to Platform Administrator.")
    return True


def promote_user_to_platform_admin(
    email: str,
    role: str = "admin",
    db: Optional[Session] = None,
    confirm: bool = True,
    target_env: Optional[str] = None,
    operator: Optional[str] = None,
) -> bool:
    """
    Promotes an existing user account to Platform Administrator or designates the first Platform Owner.
    Dual-writes is_platform_admin=True and platform_role=role atomically under transaction serialization.

    Transaction ownership contract:
    - When db is None (Script-Owned Mode, CLI usage): creates SessionLocal(), validates target_env,
      acquires the serialization lock, commits on success (return True), rolls back on failure (return False)
      or exception, and closes the session in finally.
    - When db is provided (Caller-Owned Mode): delegates to promote_user_to_platform_admin_service.
      Does not call commit() or rollback(). Caller retains full control of transaction boundaries.
      A failure does not roll back unrelated uncommitted work owned by the caller.
    """
    if db is not None:
        return promote_user_to_platform_admin_service(
            db, email=email, role=role, confirm=confirm, operator=operator, target_env=target_env
        )

    # Script-Owned Mode: validate target environment first
    resolved_env = target_env or getattr(settings, "ENVIRONMENT", "test")
    validate_bootstrap_database_target(resolved_env)

    session = SessionLocal()
    try:
        success = promote_user_to_platform_admin_service(
            session, email=email, role=role, confirm=confirm, operator=operator, target_env=resolved_env
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
        description="ROMS Platform Administrator & Owner Bootstrap Tool (OP-04).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preflight / Dry-run inspection before designating Platform Owner:
  python backend/scripts/create_platform_admin.py --target-env staging --email admin@example.com --role owner

  # Execute confirmed Platform Owner bootstrap in production:
  python backend/scripts/create_platform_admin.py --target-env production --email owner@example.com --role owner --confirm --operator "lead.ops@example.com"
        """
    )
    parser.add_argument(
        "--target-env",
        choices=["production", "staging", "development", "local", "test"],
        required=True,
        help="Explicit target environment. Required to fail closed against ambiguous database targets."
    )
    parser.add_argument("--email", required=True, help="Email address of the existing user account to promote.")
    parser.add_argument(
        "--role",
        choices=["admin", "owner"],
        default="admin",
        help="Platform role to assign: 'admin' (default) or 'owner' (first-owner bootstrap only)."
    )
    parser.add_argument("--operator", help="Identifier (name or email) of the authorized operator executing bootstrap.")
    parser.add_argument("--confirm", action="store_true", help="Explicit confirmation flag required to write database mutations.")

    args = parser.parse_args()

    # Target environment verification: MUST succeed before SessionLocal() is created
    try:
        target_info = validate_bootstrap_database_target(args.target_env)
    except Exception as e:
        print(f"\n[FATAL] Database target verification failed: {e}\n", file=sys.stderr)
        sys.exit(1)

    normalized_email = args.email.strip().lower()

    if not args.confirm:
        # Preflight Dry-Run mode
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == normalized_email).first()
            active_owners = session.query(User).filter(User.platform_role == "owner", User.status == "active").all()
            print("\n========================================================")
            print("  ROMS PLATFORM BOOTSTRAP PREFLIGHT / DRY-RUN REPORT    ")
            print("========================================================\n")
            print(f"Target Env:           {target_info.get('target_env')}")
            print(f"Target DB Host:       {target_info.get('host')}:{target_info.get('port')}")
            print(f"Target Database:      {target_info.get('database')}")
            print(f"Masked URI:           {target_info.get('masked_uri')}")
            print(f"Requested Role:       {args.role}")
            print(f"Operator:             {args.operator or 'cli_operator'}")
            if user:
                print(f"Target User Found:    {user.email} (ID: {user.id})")
                print(f"Account Status:       {user.status}")
                print(f"Current Role:         {user.platform_role}")
                print(f"Is Platform Admin:    {user.is_platform_admin}")
            else:
                print(f"Target User:          NOT FOUND ('{args.email}')")
            print(f"Active Owners Count:  {len(active_owners)}")
            for o in active_owners:
                print(f"  - {o.email} ({o.id})")
            print("--------------------------------------------------------")
            print("DRY-RUN ONLY: Zero database changes were written.")
            print("Provide --confirm to execute the role change.")
            print("========================================================\n")
            session.rollback()
            sys.exit(0)
        except Exception as e:
            session.rollback()
            print(f"\n[ERROR] Preflight inspection failed: {e}\n", file=sys.stderr)
            sys.exit(1)
        finally:
            session.close()

    # Confirmed execution
    session = SessionLocal()
    try:
        success = promote_user_to_platform_admin_service(
            db=session,
            email=args.email,
            role=args.role,
            confirm=True,
            operator=args.operator,
            target_env=args.target_env,
        )
        if success:
            session.commit()
            print("\n========================================================")
            print("  ROMS PLATFORM BOOTSTRAP COMPLETED & COMMITTED         ")
            print("========================================================\n")
            print(f"Target Env:     {target_info.get('target_env')}")
            print(f"Target DB:      {target_info.get('host')}:{target_info.get('port')}/{target_info.get('database')}")
            print(f"Target User:    {normalized_email}")
            print(f"Assigned Role:  {args.role}")
            print(f"Operator:       {args.operator or 'cli_operator'}")
            print("Status:         COMMITTED (Audit log recorded)")
            print("========================================================\n")
            sys.exit(0)
        else:
            session.rollback()
            print("\n[ERROR] Promotion failed validation. Rolled back.\n", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        session.rollback()
        print(f"\n[FATAL] Bootstrap procedure aborted: {e}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
