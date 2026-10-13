import sys
import os
import argparse
import uuid
import getpass
import socket
import re
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict, Any, List
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
from app.modules.staff.models import User
from app.modules.audit.service import log_audit
from app.modules.businesses.platform_service import _acquire_admin_serialization_lock
from app.core.errors import NotFoundError, ValidationError, ForbiddenError

VALID_TARGET_ENVIRONMENTS = ("production", "staging", "development", "local", "test")
INCIDENT_REF_PATTERN = re.compile(r"^(INC|CHG|ROMS)-\d+$", re.IGNORECASE)


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


_SENTINEL = object()


def validate_recovery_database_target(
    target_env: Optional[str],
    database_uri: Optional[str] = None,
    explicit_database_url: Any = _SENTINEL,
) -> Dict[str, Any]:
    """
    Fails closed when the database target or environment selection is ambiguous.
    Guarantees:
      1. Explicit target environment is required before any database session is created.
      2. In production or staging, implicit fallback to localhost or unconfigured database is prohibited.
      3. In production, loopback/localhost targets are prohibited.
      4. In local/development, pointing to remote cloud databases is prohibited.
      5. Sensitive credentials are fully redacted from output fields.
    """
    if not target_env or not target_env.strip():
        raise ValidationError(
            "Target environment (--target-env) is required for break-glass recovery. "
            f"Allowed environments: {list(VALID_TARGET_ENVIRONMENTS)}"
        )

    clean_env = target_env.strip().lower()
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
                "Implicit fallback to default localhost settings is prohibited in recovery mode."
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

    # Build masked URI
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


def diagnose_platform_state(db: Session, target_env: Optional[str] = None) -> Dict[str, Any]:
    """
    Stage A — Diagnostic Inspection (Read-Only).
    Analyzes the current platform governance state, database configuration,
    and platform-user distribution without executing any database mutations.
    """
    # 1. Database connection target
    masked_uri = getattr(settings, "MASKED_DATABASE_URI", "hidden")

    # 2. Query platform-role counts
    active_owners = (
        db.query(User)
        .filter(User.platform_role == "owner", User.status == "active")
        .order_by(User.created_at.asc())
        .all()
    )
    suspended_owners = (
        db.query(User)
        .filter(User.platform_role == "owner", User.status == "suspended")
        .order_by(User.created_at.asc())
        .all()
    )
    active_admins = (
        db.query(User)
        .filter(User.platform_role == "admin", User.status == "active")
        .order_by(User.created_at.asc())
        .all()
    )
    suspended_admins = (
        db.query(User)
        .filter(User.platform_role == "admin", User.status == "suspended")
        .order_by(User.created_at.asc())
        .all()
    )
    active_operators = (
        db.query(User)
        .filter(User.platform_role == "operator", User.status == "active")
        .order_by(User.created_at.asc())
        .all()
    )

    active_owner_count = len(active_owners)
    suspended_owner_count = len(suspended_owners)

    # 3. Determine governance health status
    if active_owner_count == 1:
        health_status = "HEALTHY"
        governance_operational = True
        summary = "Normal platform governance is operational (exactly 1 active Platform Owner)."
    elif active_owner_count == 0 and suspended_owner_count > 0:
        health_status = "OWNER_SUSPENDED"
        governance_operational = False
        summary = (
            "Platform Owner account is suspended (0 active owners). "
            "Governance endpoints return HTTP 503. Break-glass reactivation or replacement required."
        )
    elif active_owner_count == 0:
        health_status = "ZERO_OWNER_ORPHANED"
        governance_operational = False
        summary = (
            "Zero active Platform Owners exist in the system. "
            "Governance endpoints return HTTP 503. Break-glass owner designation required."
        )
    else:
        health_status = "ANOMALOUS_MULTIPLE_OWNERS"
        governance_operational = False
        summary = (
            f"Anomalous state: {active_owner_count} active Platform Owners detected. "
            "Violates single-active-Owner invariant. Immediate manual escalation required."
        )

    return {
        "target_environment": target_env or getattr(settings, "ENVIRONMENT", "unspecified"),
        "database_target": masked_uri,
        "health_status": health_status,
        "governance_operational": governance_operational,
        "summary": summary,
        "active_owners": [{"id": str(u.id), "email": u.email, "display_name": u.display_name} for u in active_owners],
        "suspended_owners": [{"id": str(u.id), "email": u.email, "display_name": u.display_name} for u in suspended_owners],
        "active_admins_count": len(active_admins),
        "suspended_admins_count": len(suspended_admins),
        "active_operators_count": len(active_operators),
    }


def _resolve_target_user(db: Session, identifier: str) -> User:
    """Helper to resolve a target user by UUID string or email."""
    clean = identifier.strip()
    try:
        user_uuid = uuid.UUID(clean)
        user = db.query(User).populate_existing().filter(User.id == user_uuid).first()
        if user:
            return user
    except (ValueError, AttributeError):
        pass

    user = db.query(User).populate_existing().filter(User.email == clean.lower()).first()
    if not user:
        raise NotFoundError(f"Target user '{clean}' not found.")
    return user


def execute_break_glass_recovery(
    db: Session,
    action: str,
    operator: str,
    incident_ref: str,
    target_identifier: Optional[str] = None,
    new_password: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    Core domain service implementing the restricted break-glass recovery workflow.
    Stages:
      Stage A — Diagnose: inspects platform state.
      Stage B — Authorize: enforces operator, incident ref, target validation, and dry-run guard.
      Stage C — Recover: executes narrowly authorized mutation under serialization lock.
      Stage D — Verify & Close: verifies post-condition invariant and commits audit record.

    Session Ownership Contract:
    - Receives a caller-owned Session 'db'.
    - If confirm is False, acts as a pure dry-run (zero mutations committed, rollback on exit).
    - If confirm is True, performs lock acquisition, validation, mutations, flush(), post-verification,
      and audit logging.
    - Does NOT call commit() or close() directly; leaves boundary control to the caller/CLI runner.
    """
    clean_action = action.strip().lower() if action else "diagnose"
    if clean_action == "reset-credentials":
        raise ValidationError(
            "Recovery action 'reset-credentials' is disabled due to credential exposure risks. "
            "To recover access, use 'replace-owner' to designate an active Administrator as Owner."
        )
    if new_password is not None:
        raise ValidationError(
            "Argument 'new_password' is not supported; credential reset has been disabled."
        )
    valid_actions = ("diagnose", "replace-owner", "reactivate-owner")
    if clean_action not in valid_actions:
        raise ValidationError(f"Invalid recovery action '{action}'. Allowed actions: {valid_actions}")

    # Stage A: Preflight Diagnostic
    diag = diagnose_platform_state(db)

    if clean_action == "diagnose":
        return {
            "stage": "A_DIAGNOSE",
            "action": "diagnose",
            "dry_run": True,
            "outcome": "completed",
            "diagnosis": diag,
        }

    # Stage B: Authorization Gates
    if not operator or not operator.strip():
        raise ValidationError("Operator identity (--operator) is required for recovery operations.")
    clean_operator = operator.strip()

    if not incident_ref or not incident_ref.strip():
        raise ValidationError("Documented incident/change reference (--incident-ref) is required for recovery operations.")
    clean_incident = incident_ref.strip()
    if not INCIDENT_REF_PATTERN.match(clean_incident):
        raise ValidationError(
            f"Invalid incident reference format '{clean_incident}'. "
            "Must match pattern '^(INC|CHG|ROMS)-<digits>' (e.g. 'INC-1001', 'CHG-2002', 'ROMS-48201')."
        )

    if not target_identifier or not target_identifier.strip():
        raise ValidationError(f"Target user (--target) is required for action '{clean_action}'.")
    clean_target_id = target_identifier.strip()

    target = _resolve_target_user(db, clean_target_id)

    # Dry-Run Guard: If --confirm is not explicitly set, show proposed changes and exit safely
    if not confirm:
        return {
            "stage": "B_AUTHORIZE_DRY_RUN",
            "action": clean_action,
            "operator": clean_operator,
            "incident_ref": clean_incident,
            "target": {"id": str(target.id), "email": target.email, "current_role": target.platform_role, "status": target.status},
            "dry_run": True,
            "outcome": "dry_run_completed",
            "message": "Dry-run completed successfully. Zero changes were written. Provide --confirm to execute recovery.",
            "diagnosis": diag,
        }

    # Stage C: Execute Narrowly Authorized Recovery Under Serialization Lock
    _acquire_admin_serialization_lock(db)

    # Reload target under lock
    target = db.query(User).populate_existing().filter(User.id == target.id).first()
    if not target:
        raise NotFoundError(f"Target user '{clean_target_id}' not found under serialization lock.")

    affected_users = []
    previous_owner_info = None

    if clean_action == "replace-owner":
        # Target must be an active user
        if target.status != "active":
            raise ValidationError(
                f"Cannot promote user '{target.email}' with status '{target.status}' to Platform Owner. "
                "Target account must be active."
            )

        # Target must currently be a Platform Admin (cannot promote operators or non-admins directly)
        if target.platform_role != "admin" or not target.is_platform_admin:
            if target.platform_role == "owner":
                return {
                    "stage": "C_RECOVER",
                    "action": clean_action,
                    "operator": clean_operator,
                    "incident_ref": clean_incident,
                    "dry_run": False,
                    "outcome": "noop",
                    "message": f"Target user '{target.email}' is already the active Platform Owner. No changes needed.",
                }
            raise ValidationError(
                f"Cannot promote user '{target.email}' with platform_role '{target.platform_role}' to Platform Owner. "
                "Target must be an active Platform Administrator (platform_role='admin')."
            )

        # Find existing active owner(s) and demote to admin
        existing_owners = (
            db.query(User)
            .populate_existing()
            .filter(User.platform_role == "owner", User.status == "active")
            .all()
        )
        for old_owner in existing_owners:
            if old_owner.id != target.id:
                old_owner.platform_role = "admin"
                old_owner.is_platform_admin = True
                db.flush()
                affected_users.append(old_owner)
                previous_owner_info = {"id": str(old_owner.id), "email": old_owner.email}

        # Promote target to owner
        target.platform_role = "owner"
        target.is_platform_admin = True
        db.flush()
        affected_users.append(target)

    elif clean_action == "reactivate-owner":
        # Target must be an owner currently suspended
        if target.platform_role != "owner":
            raise ValidationError(
                f"User '{target.email}' does not hold platform_role='owner' (found: '{target.platform_role}'). "
                "Action 'reactivate-owner' only applies to Platform Owners."
            )

        if target.status == "active":
            return {
                "stage": "C_RECOVER",
                "action": clean_action,
                "operator": clean_operator,
                "incident_ref": clean_incident,
                "dry_run": False,
                "outcome": "noop",
                "message": f"Platform Owner '{target.email}' is already active. No changes needed.",
            }

        # Verify no other active owner exists
        active_count = db.query(User).filter(User.platform_role == "owner", User.status == "active").count()
        if active_count > 0:
            raise ValidationError(
                f"Cannot reactivate Platform Owner '{target.email}': another active Platform Owner already exists."
            )

        target.status = "active"
        target.is_platform_admin = True
        db.flush()
        affected_users.append(target)

    # Stage D: Post-Recovery Invariant Verification
    post_active_owners = (
        db.query(User)
        .populate_existing()
        .filter(User.platform_role == "owner", User.status == "active")
        .all()
    )
    if len(post_active_owners) != 1:
        raise RuntimeError(
            f"Post-recovery invariant violation: expected exactly 1 active Platform Owner, "
            f"found {len(post_active_owners)}. Aborting and rolling back transaction."
        )

    # Record Audit Log (strictly excluding passwords, secrets, and credentials)
    exec_context = _get_execution_context()
    audit_metadata = {
        "recovery_stage": "STAGE_C_RECOVER",
        "action_type": clean_action,
        "operator": clean_operator,
        "operator_system_user": exec_context.get("os_user"),
        "execution_host": exec_context.get("hostname"),
        "incident_ref": clean_incident,
        "target_user_id": str(target.id),
        "target_email": target.email,
        "new_platform_role": target.platform_role,
        "new_status": target.status,
        "previous_owner": previous_owner_info,
        "outcome": "success",
    }
    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=None,
        action="platform.recovery.break_glass",
        entity_type="user",
        entity_id=target.id,
        metadata_json=audit_metadata,
    )

    return {
        "stage": "D_VERIFY_AND_CLOSE",
        "action": clean_action,
        "operator": clean_operator,
        "operator_system_user": exec_context.get("os_user"),
        "execution_host": exec_context.get("hostname"),
        "incident_ref": clean_incident,
        "target": {"id": str(target.id), "email": target.email, "role": target.platform_role, "status": target.status},
        "previous_owner": previous_owner_info,
        "active_owner_count": len(post_active_owners),
        "dry_run": False,
        "outcome": "success",
        "message": f"Break-glass recovery '{clean_action}' executed and verified successfully.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="ROMS Restricted CLI Break-Glass Recovery Tool (OP-03).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stage A: Run read-only diagnosis against staging
  python backend/scripts/break_glass_recovery.py --target-env staging --diagnose

  # Stage B: Authorize and Dry-Run replacing an incapacitated owner in production
  python backend/scripts/break_glass_recovery.py --target-env production --action replace-owner --operator "alice.ops" --incident-ref "INC-1001" --target "admin@test.com"

  # Stage C & D: Execute with explicit confirmation in production
  python backend/scripts/break_glass_recovery.py --target-env production --action replace-owner --operator "alice.ops" --incident-ref "INC-1001" --target "admin@test.com" --confirm

Security Notice:
  Action 'reset-credentials' is intentionally DISABLED in this tool due to credential exposure risks.
  To recover access for a locked-out platform, use 'replace-owner' to designate a trusted Administrator as Owner.
        """
    )
    parser.add_argument(
        "--target-env",
        choices=["production", "staging", "development", "local", "test"],
        required=True,
        help="Explicit target environment. Required to fail closed against ambiguous database targets."
    )
    parser.add_argument("--diagnose", action="store_true", help="Execute read-only Stage A diagnostic inspection and exit.")
    parser.add_argument(
        "--action",
        choices=["diagnose", "replace-owner", "reactivate-owner"],
        default="diagnose",
        help="Recovery action to perform (default: 'diagnose')."
    )
    parser.add_argument("--operator", help="Identifier (name or email) of the authorized operator executing recovery.")
    parser.add_argument("--incident-ref", help="Documented incident ticket or change reference matching ^(INC|CHG|ROMS)-<digits> (e.g. INC-12345).")
    parser.add_argument("--target", help="Target user email address or UUID.")
    parser.add_argument("--confirm", action="store_true", help="Explicit confirmation flag required to write database mutations.")

    args = parser.parse_args()

    action = "diagnose" if args.diagnose else args.action

    # Target environment verification: MUST succeed before SessionLocal() is created
    try:
        target_info = validate_recovery_database_target(args.target_env)
    except Exception as e:
        print(f"\n[FATAL] Database target verification failed: {e}\n", file=sys.stderr)
        sys.exit(1)

    session = SessionLocal()
    try:
        result = execute_break_glass_recovery(
            db=session,
            action=action,
            operator=args.operator or "",
            incident_ref=args.incident_ref or "",
            target_identifier=args.target,
            confirm=args.confirm,
        )

        if args.confirm and action != "diagnose":
            session.commit()
            print("\n========================================================")
            print("  ROMS BREAK-GLASS RECOVERY COMPLETED & COMMITTED       ")
            print("========================================================")
            print(f"Target Env:   {target_info.get('target_env')}")
            print(f"Target DB:    {target_info.get('host')}:{target_info.get('port')}/{target_info.get('database')}")
            print(f"Outcome:      {result.get('outcome')}")
            print(f"Action:       {result.get('action')}")
            print(f"Operator:     {result.get('operator')}")
            print(f"OS User:      {result.get('operator_system_user')}")
            print(f"Host:         {result.get('execution_host')}")
            print(f"Incident:     {result.get('incident_ref')}")
            print(f"Target User:  {result.get('target', {}).get('email')} ({result.get('target', {}).get('id')})")
            print(f"Resulting Role: {result.get('target', {}).get('role')}")
            print(f"Active Owners:{result.get('active_owner_count')}")
            print(f"Message:      {result.get('message')}")
            print("========================================================\n")
        else:
            session.rollback()
            print("\n========================================================")
            print("  ROMS BREAK-GLASS DIAGNOSTIC / DRY-RUN REPORT          ")
            print("========================================================")
            print(f"Target Env:           {target_info.get('target_env')}")
            print(f"Target DB Host:       {target_info.get('host')}:{target_info.get('port')}")
            print(f"Target Database:      {target_info.get('database')}")
            print(f"Masked URI:           {target_info.get('masked_uri')}")
            if action == "diagnose":
                diag = result.get("diagnosis", {})
                print(f"Governance Status:    {diag.get('health_status')}")
                print(f"Operational:          {diag.get('governance_operational')}")
                print(f"Summary:              {diag.get('summary')}")
                print(f"Active Owners:        {len(diag.get('active_owners', []))}")
                for o in diag.get('active_owners', []):
                    print(f"  - {o['email']} ({o['id']})")
                print(f"Suspended Owners:     {len(diag.get('suspended_owners', []))}")
                for so in diag.get('suspended_owners', []):
                    print(f"  - {so['email']} ({so['id']})")
                print(f"Active Admins:        {diag.get('active_admins_count')}")
                print(f"Active Operators:     {diag.get('active_operators_count')}")
            else:
                print(f"Stage:        {result.get('stage')}")
                print(f"Action:       {result.get('action')}")
                print(f"Operator:     {result.get('operator')}")
                print(f"OS User:      {result.get('operator_system_user')}")
                print(f"Host:         {result.get('execution_host')}")
                print(f"Incident:     {result.get('incident_ref')}")
                print(f"Target:       {result.get('target')}")
                print(f"Notice:       {result.get('message')}")
            print("========================================================\n")

        sys.exit(0)
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Recovery procedure aborted: {e}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
