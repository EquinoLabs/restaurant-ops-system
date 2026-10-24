"""Secure temporary credential management for approvals-based provisioning.

Generates cryptographically random temporary credentials and safely delivers
them to restricted local developer artifacts without logging or storing
plaintext secrets in the database.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import secrets
import string

CREDENTIALS_FILENAME = ".local-user-credentials.txt"


def generate_secure_temporary_password(length: int = 18) -> str:
    """Generate a high-entropy, cryptographically random temporary password.

    Ensures at least one uppercase, lowercase, digit, and symbol character.
    Never hardcoded and never logged.
    """
    if length < 14:
        length = 14

    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*-_=+"

    # Ensure representation from each character class
    password_chars = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_chars = upper + lower + digits + symbols
    password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]

    # Shuffle characters using secrets.SystemRandom
    rng = secrets.SystemRandom()
    rng.shuffle(password_chars)
    return "".join(password_chars)


def deliver_local_credential_artifact(
    *,
    request_id: str,
    user_id: str,
    email: str,
    role: str = "operator",
    display_name: str | None = None,
    temp_password: str,
    target_dir: str | Path | None = None,
) -> Path:
    """Deliver generated credentials to a restricted local development artifact.

    Format:
    [{ISO_UTC}] REQUEST_ID={request_id} | USER_ID={user_id} | EMAIL={email} | ROLE={role} | DISPLAY_NAME="{display_name}" | TEMP_PASSWORD="{temp_password}"

    Ensures:
    1. File is saved under backend/ directory (or specified target_dir).
    2. File permissions are restricted to user-only (0o600) on platforms supporting chmod.
    3. Prevents duplicate credentials line if USER_ID has already been written.
    4. Plaintext password is NEVER logged to python logging or standard output.
    """
    if target_dir is None:
        # Default to backend root directory (app/modules/approvals/credentials.py -> 4 levels up to backend)
        target_dir = Path(__file__).resolve().parent.parent.parent.parent
    else:
        target_dir = Path(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / CREDENTIALS_FILENAME

    # Check for existing record to avoid appending duplicate/conflicting credentials
    target_marker = f"USER_ID={user_id}"
    if file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
            if target_marker in content:
                # User credential was already recorded; do not overwrite or duplicate
                return file_path
        except Exception:
            pass

    now_utc = datetime.now(timezone.utc).isoformat()
    clean_display = (display_name or "").replace('"', '\\"')
    record = (
        f"[{now_utc}] REQUEST_ID={request_id} | USER_ID={user_id} | EMAIL={email} | "
        f'ROLE={role} | DISPLAY_NAME="{clean_display}" | TEMP_PASSWORD="{temp_password}"\n'
    )

    # Open with exclusive or append permissions
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(record)

    # Restrict permissions to owner read/write (0o600) where supported
    try:
        os.chmod(file_path, 0o600)
    except Exception:
        # Windows chmod has limited capability, ignore if unsupported
        pass

    return file_path
