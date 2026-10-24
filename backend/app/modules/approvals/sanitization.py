"""Sanitization and validation rules for approval request snapshots and execution diagnostics.

Ensures that sensitive data (passwords, tokens, API keys, connection strings, session cookies, etc.)
are never persisted in approval payloads, previous state snapshots, or execution error diagnostics.
Uses request-type-specific field allowlists and recursive scrubbing to guarantee safety.
"""
from typing import Any, Dict, Optional, Set
import re

# Comprehensive denylist for generic scrubbing of dictionary keys
FORBIDDEN_KEY_PATTERNS = {
    "password",
    "password_hash",
    "owner_password",
    "current_password",
    "new_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "connection_string",
    "database_uri",
    "sqlalchemy_database_uri",
    "private_key",
}

# Request-type-specific field allowlists defining exactly what fields can exist in payload_snapshot
REQUEST_PAYLOAD_ALLOWLISTS: Dict[str, Set[str]] = {
    "business_creation": {
        "name",
        "legal_name",
        "phone",
        "email",
        "owner_email",
        "owner_display_name",
        # NOTE: owner_password is NEVER allowed in payload_snapshot
    },
    "outlet_creation": {
        "business_id",
        "name",
        "public_slug",
        "currency",
        "timezone",
        "address",
        "manager_email",
        "manager_display_name",
    },
    "user_role_change": {
        "target_user_id",
        "new_platform_role",
        "target_email",
    },
    "subscription_change": {
        "business_id",
        "outlet_id",
        "plan_code",
        "action_type",
        "billing_interval",
        "reason",
        "max_outlets",
    },
    "operator_creation": {
        "email",
        "display_name",
        "target_user_id",
        # NOTE: password is NEVER allowed
    },
    "operator_revocation": {
        "target_user_id",
        "target_email",
    },
    "user_suspension": {
        "target_user_id",
        "target_email",
        "reason",
    },
    "user_reactivation": {
        "target_user_id",
        "target_email",
        "reason",
    },
}

# Regex to detect connection strings, JWTs, or private keys in raw strings
SENSITIVE_STRING_PATTERNS = [
    re.compile(r"postgres(ql)?://[^\s'\"]+:[^\s'\"]+@", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9\-_.]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
]


def contains_forbidden_keys(data: Any) -> bool:
    """
    Recursively scans nested structures (dicts, lists) for any forbidden key names.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            if any(forbidden in k_lower for forbidden in FORBIDDEN_KEY_PATTERNS):
                return True
            if contains_forbidden_keys(v):
                return True
    elif isinstance(data, list):
        for item in data:
            if contains_forbidden_keys(item):
                return True
    return False


def validate_and_sanitize_payload(request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates that payload contains only allowed fields for the request_type and no sensitive values.
    Returns a clean, shallow-copied dictionary.
    Raises ValueError if unauthorized or sensitive fields are present.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload snapshot must be a valid JSON dictionary.")

    # 1. Check for any forbidden key names recursively
    if contains_forbidden_keys(payload):
        raise ValueError("Payload contains forbidden sensitive fields (passwords, tokens, or credentials).")

    # 2. Enforce request-type-specific allowlist if defined
    allowed_fields = REQUEST_PAYLOAD_ALLOWLISTS.get(request_type)
    if allowed_fields is not None:
        extra_keys = set(payload.keys()) - allowed_fields
        if extra_keys:
            raise ValueError(
                f"Payload for request type '{request_type}' contains unauthorized fields: {sorted(extra_keys)}"
            )

    return dict(payload)


def sanitize_diagnostic_message(error: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Sanitizes diagnostic error strings, truncating length, masking DB connection strings / auth headers,
    and preventing raw stack traces or internal secrets from leaking into execution_error.
    """
    if not error:
        return None

    sanitized = str(error)

    # Mask connection URIs
    for pattern in SENSITIVE_STRING_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)

    # Truncate to safe bound
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [TRUNCATED]"

    return sanitized


def sanitize_diagnostic_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Recursively sanitizes execution diagnostic details JSON, stripping any sensitive keys
    and replacing string values matching sensitive patterns.
    """
    if details is None:
        return None

    if not isinstance(details, dict):
        return {"diagnostic": str(details)[:500]}

    def _clean(val: Any) -> Any:
        if isinstance(val, dict):
            cleaned = {}
            for k, v in val.items():
                k_lower = str(k).lower().strip()
                if any(forbidden in k_lower for forbidden in FORBIDDEN_KEY_PATTERNS):
                    cleaned[k] = "[REDACTED]"
                else:
                    cleaned[k] = _clean(v)
            return cleaned
        elif isinstance(val, list):
            return [_clean(x) for x in val]
        elif isinstance(val, str):
            res = val
            for pattern in SENSITIVE_STRING_PATTERNS:
                res = pattern.sub("[REDACTED_SECRET]", res)
            return res[:500]
        return val

    return _clean(details)
