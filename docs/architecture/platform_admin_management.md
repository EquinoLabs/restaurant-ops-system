# Platform-Admin Management & Last-Admin Protection Architecture

> **Current-versus-target note (2026-10-17):** This document describes the shipped **legacy boolean-flag** platform-admin management endpoints (`is_platform_admin` grant/revoke with last-active-admin protection). Since this document was written, the three-tier platform plane (`platform_roles` + `RequirePlatformRole` in `backend/app/api/deps.py`, governance routers in `backend/app/api/v1/platform.py`) has been implemented and is the primary platform authorization mechanism. The grant/revoke endpoints and audit actions described here remain shipped and accurate for the legacy flags; where this document says authorization is `get_current_platform_admin`, treat that as the historical dependency name — current platform routers enforce `RequirePlatformRole`. The authoritative Stage 3 target architecture (business ownership, outlet-scoped subscriptions, read-only Operators) is `docs/architecture/stage_3_ownership_subscriptions_architecture.md`. This document does not describe Stage 3 features, which are **not implemented**.

## 1. Overview

ROMS provides secure management of platform administrator privileges, ensuring system-wide administrative governance and preventing accidental platform lockouts via concurrency-safe last-active-admin protection.

---

## 2. Definition of an Active Platform Administrator

An **Active Platform Administrator** is defined as a user record satisfying both database constraints:
- `User.is_platform_admin == True`
- `User.status == "active"`

Users with `is_platform_admin == True` whose account `status` is set to `"suspended"` or any non-active state are not considered active administrators and cannot pass the `get_current_platform_admin` authentication dependency.

---

## 3. Endpoints & Authorization Rules

All platform admin management endpoints require active-platform-administrator authentication via JWT tokens (historically the `get_current_platform_admin` dependency; current platform-plane routers enforce `RequirePlatformRole` — see the note above):

| Endpoint Path | Method | Description | Response Schema |
| :--- | :--- | :--- | :--- |
| `/api/v1/platform/admins` | `GET` | Lists all users with platform admin privileges. Excludes password hashes and secrets. | `List[PlatformAdminUserOut]` |
| `/api/v1/platform/admins/{user_id}/grant` | `POST` | Grants platform admin privileges (`is_platform_admin = True`) to an existing user. | `PlatformAdminUserOut` |
| `/api/v1/platform/admins/{user_id}/revoke` | `POST` | Revokes platform admin privileges (`is_platform_admin = False`), subject to last-admin protection. | `PlatformAdminUserOut` |

---

## 4. Last-Active-Admin Protection & Concurrency Strategy

### Protection Invariant
The system must never allow an operation to leave zero active platform administrators in the database.

### Concurrency Strategy: Pessimistic Row-Level Locking
To protect against race conditions where two concurrent requests attempt to demote the last remaining admins simultaneously:

1. The target `User` row is queried with `with_for_update()`.
2. If `target_user.is_platform_admin == True` and `target_user.status == "active"`:
   - The system acquires exclusive row locks on all active admin rows:
     ```python
     active_admins = db.query(User).filter(
         User.is_platform_admin == True,
         User.status == "active"
     ).with_for_update().all()
     ```
   - If `len(active_admins) <= 1`:
     - The demotion request is rejected with `HTTP 422 / ValidationError("Cannot revoke platform admin privileges from the last active platform administrator.")`.
3. If `len(active_admins) > 1`, `target_user.is_platform_admin` is updated to `False`.

### Database Safety Guarantee
In PostgreSQL, `SELECT ... FOR UPDATE` locks the selected rows until the current SQL transaction commits or rolls back. Competing transactions wait for the lock release. When the second transaction acquires the lock, it evaluates the fresh DB state (`active_admins_count == 1`) and safely fails validation.

---

## 5. Audit Logging & Transaction Atomicity

- **Action Identifiers**:
  - `platform.admin.grant`: Emitted when platform admin privileges are granted.
  - `platform.admin.revoke`: Emitted when platform admin privileges are revoked.
- **Metadata**:
  - `actor_user_id`: Sourced exclusively from `current_user.id` (`get_current_platform_admin`).
  - `metadata_json`: `{"outcome": "success", "target_user_id": str(target_user.id), "target_email": target_user.email}`.
  - No passwords or secrets are recorded.
- **Atomicity**:
  - Operational privilege changes and `log_audit()` calls execute within the same database transaction.
  - `db.commit()` commits both the user privilege update and the audit log entry atomically.
  - Rejected demotion attempts roll back cleanly without generating false success audit events.
- **No-Op Handling**:
  - If a user is already a platform admin when `grant` is called (or already not an admin when `revoke` is called), the service returns the user as a no-op without emitting duplicate audit events.

---

## 6. CLI Bootstrap Compatibility

- Initial platform administrator promotion is maintained via the existing CLI script (`scripts/create_platform_admin.py`).
- Automatic environment-variable promotion at application startup is intentionally omitted to maintain deterministic access control.

---

## 7. Known Testing & Operational Limitations

- **Concurrency Simulation in In-Memory SQLite**: Unit tests run against SQLite in-memory with `StaticPool`. SQLite enforces single-writer database locking. Full PostgreSQL `SELECT FOR UPDATE` row locking is verified in PostgreSQL deployment environments.

---

## 8. Stage 3 Alignment Notes (Target — Not Implemented)

The following corrections and boundaries are recorded for consistency with Owner Decisions 002–004 and `docs/architecture/stage_3_ownership_subscriptions_architecture.md`. Nothing in this section is shipped.

1. **Business ownership ≠ platform-plane ownership.** The ownership-transfer ceremony and single-active-owner invariant in the three-tier model concern the **platform plane** (`platform.owner.transfer`). **Business ownership** (one owner per business, transfer demotes the previous owner to manager) is a separate, tenant-level concept using the audit action `platform.business_owner.transfer`. The two must never be conflated in logs, endpoints, or documentation.
2. **Initial owner passwords.** Business creation sets the initial owner password via the Platform Admin portal (Decision 003). No forced first-login change; no email/reset/invitation flows in this phase. Passwords are never logged, never audited, and never echoed in error responses — consistent with the "No passwords or secrets are recorded" rule in §5.
3. **Platform Operator permissions.** Operators are strictly read-only (Decision 004). This document does not grant Operators any write capability; the Team administration endpoints above are Owner/Admin-only.
4. **Zero-owner businesses are report-only.** Distinct from the last-active-admin protection in §4: the §4 invariant protects the platform plane; tenant businesses with zero owners are detected by reconciliation reporting and are **not** auto-repaired.
