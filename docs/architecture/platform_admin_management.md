# Platform-Admin Management & Last-Admin Protection Architecture

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

All platform admin management endpoints require `get_current_platform_admin` dependency authorization (which enforces active platform admin authentication via JWT tokens):

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
