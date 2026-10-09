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
from app.db.session import SessionLocal
from app.modules.staff.models import User




def promote_user_to_platform_admin(email: str, db=None) -> bool:
    """
    Promotes an existing user account to Platform Administrator by email.
    Returns True if user promoted successfully, False if user not found.
    """
    normalized_email = email.strip().lower()
    close_db = False

    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        user = db.query(User).filter(User.email == normalized_email).first()
        if not user:
            print(f"Error: User with email '{normalized_email}' was not found.")
            print("Please create the user account first before promoting to platform administrator.")
            return False

        if user.is_platform_admin:
            print(f"Notice: User '{normalized_email}' is already a Platform Administrator.")
            return True

        user.is_platform_admin = True
        db.commit()
        db.refresh(user)
        print(f"Success: User '{normalized_email}' (ID: {user.id}) has been promoted to Platform Administrator.")
        return True
    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Promote an existing ROMS user to Platform Administrator.")
    parser.add_argument("--email", required=True, help="Email address of the existing user account to promote.")
    args = parser.parse_args()

    success = promote_user_to_platform_admin(args.email)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
