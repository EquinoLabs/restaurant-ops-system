import sys
import os
import argparse

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
from app.modules.staff.models import User
from app.modules.businesses.platform_service import _acquire_admin_serialization_lock


def promote_user_to_platform_admin_service(db: Session, email: str, role: str = "admin") -> bool:
    """
    Core domain service that promotes an existing user account to Platform Administrator
    or designates the first Platform Owner within an existing caller-owned session.
    Dual-writes is_platform_admin=True and platform_role=role atomically under transaction serialization.

    Session Ownership Contract:
    - Receives a caller-owned Session 'db'.
    - Performs validation, advisory lock acquisition, ORM mutations, and flush().
    - NEVER calls commit() or rollback().
    - Caller retains full control over transaction boundaries, commit, rollback, and session closure.
    - Returns True on successful promotion or safe idempotent no-op.
    - Returns False on validation failure (invalid role, user not found, non-active account, second owner attempt).
    """
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

    _acquire_admin_serialization_lock(db)

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        print(f"Error: User with email '{normalized_email}' was not found.")
        print("Please create the user account first before promoting to platform administrator.")
        return False

    if user.status != "active":
        print(f"Error: User '{normalized_email}' account status is '{user.status}'. Only 'active' accounts can be promoted.")
        return False

    if normalized_role == "owner":
        active_owners = (
            db.query(User)
            .filter(User.platform_role == "owner", User.status == "active")
            .all()
        )
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
    print(f"Success: User '{normalized_email}' (ID: {user.id}) has been promoted to Platform Administrator.")
    return True


def promote_user_to_platform_admin(email: str, role: str = "admin", db=None) -> bool:
    """
    Promotes an existing user account to Platform Administrator or designates the first Platform Owner.
    Dual-writes is_platform_admin=True and platform_role=role atomically under transaction serialization.

    Transaction ownership contract:
    - When db is None (Script-Owned Mode, CLI usage): creates SessionLocal(), acquires the serialization lock,
      commits on success (return True), rolls back on failure (return False) or exception, and closes the session in finally.
    - When db is provided (Caller-Owned Mode): delegates to promote_user_to_platform_admin_service.
      Does not call commit() or rollback(). Caller retains full control of transaction boundaries.
      A failure does not roll back unrelated uncommitted work owned by the caller.
    """
    if db is not None:
        return promote_user_to_platform_admin_service(db, email=email, role=role)

    session = SessionLocal()
    try:
        success = promote_user_to_platform_admin_service(session, email=email, role=role)
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
    parser = argparse.ArgumentParser(description="Promote an existing ROMS user to Platform Administrator or Owner.")
    parser.add_argument("--email", required=True, help="Email address of the existing user account to promote.")
    parser.add_argument(
        "--role",
        choices=["admin", "owner"],
        default="admin",
        help="Platform role to assign: 'admin' (default) or 'owner' (first-owner bootstrap only)."
    )
    args = parser.parse_args()

    success = promote_user_to_platform_admin(args.email, role=args.role)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
