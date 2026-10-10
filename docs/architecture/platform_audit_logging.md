# Platform Audit Logging Architecture

## 1. Overview

ROMS (Restaurant Operations Management System) records audit logs for administrative actions taken by platform administrators. Audit entries are persisted to the central `audit_logs` table.

---

## 2. Audited Operations & Action Naming Conventions

All platform audit actions use the `platform.<domain>.<verb>` naming scheme:

| Operation | Action Identifier | Entity Type | Target Business ID | Target Outlet ID | Description & Metadata Captured |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Business Creation** | `platform.business.create` | `business` | `business.id` | `primary_outlet.id` | Records provisioning of a business and its primary outlet. Includes plan name, max outlets, subscription status, and public slug. |
| **Subscription Update** | `platform.business.update_subscription` | `business` | `business.id` | `None` | Records changes to subscription status, plan name, max outlets, or trial end dates. Includes before and after state snapshots. |
| **Business Suspension** | `platform.business.suspend` | `business` | `business.id` | `None` | Triggered when account status transitions to `"suspended"`. Includes before and after state snapshots. |
| **Business Reactivation** | `platform.business.reactivate` | `business` | `business.id` | `None` | Triggered when account status transitions from `"suspended"` to `"active"`. Includes before and after state snapshots. |
| **Outlet Creation** | `platform.outlet.create` | `outlet` | `business.id` | `outlet.id` | Records creation of additional outlets under a business. Includes outlet name, public slug, currency, and timezone. |
| **Owner Assignment** | `platform.owner.assign` | `membership` | `business.id` | `outlet.id` | Records assignment or creation of an owner user for an outlet. Includes assigned user ID, email, role, and boolean flag `created_new_user`. |

---

## 3. Database Schema & Fields

Audit records use the standard `AuditLog` model (`audit_logs` table):

- **`id`** (`UUID`): Primary key.
- **`business_id`** (`UUID`, non-null, indexed): The target business ID associated with the operation.
- **`outlet_id`** (`UUID`, nullable, indexed): The target outlet ID, when applicable.
- **`actor_user_id`** (`UUID`, nullable, indexed): The authenticated platform admin's user ID (from `current_user.id`).
- **`action`** (`VARCHAR(100)`): Machine-readable action name (e.g., `platform.business.suspend`).
- **`entity_type`** (`VARCHAR(100)`): Entity affected (`business`, `outlet`, or `membership`).
- **`entity_id`** (`UUID`): Primary key of the affected entity.
- **`metadata_json`** (`JSON`): Structured metadata containing outcome status (`"success"`), before/after state snapshots, and context.
- **`created_at`** (`TIMESTAMP`): Server-side timestamp generated upon record creation.

---

## 4. Transaction Boundaries & Failure Handling

1. **Transactional Atomicity**:
   - Operational changes and the corresponding `log_audit()` invocation occur within the **same database transaction**.
   - A single `db.commit()` persists both the business domain changes and the audit record.
2. **Rollback Behavior**:
   - If validation fails, or if a database constraint exception occurs prior to commit, `db.rollback()` discards both the entity mutation and the audit entry.
   - Operations that fail or abort never leave a false success audit entry in the database.
3. **Double-Logging Prevention**:
   - Audit entries are emitted exclusively within `platform_service.py` functions to prevent duplicate entries from API route handlers.

---

## 5. Security & Sensitive Information Exclusion

The following sensitive fields are **strictly prohibited** from appearing in audit `metadata_json` or any audit fields:

- Passwords and raw authentication credentials.
- Password hashes (`password_hash`).
- Access tokens, refresh tokens, JWTs.
- R2 credentials, API keys, database connection strings.

When a new owner user is created via `platform.owner.assign`, the user's password is hashed and stored in `users`, but the audit payload records only `assigned_user_id`, `email`, `role`, and `created_new_user`.

---

## 6. Access Control & Tenant Isolation

- Platform audit operations require `get_current_platform_admin` dependency authentication.
- Ordinary business admins and staff users cannot trigger platform audit events.
- Platform audit logs are not exposed to tenant business users or staff via standard outlet endpoints (`/outlets/{id}/audit-logs` returns only outlet-scoped menu audit events).

---

## 7. Current Limitations

- **Failed Request Auditing**: Unauthenticated requests or invalid request payloads (400/401/403/422 validation failures) fail before reaching service execution and are not persisted as audit entries in the database.
- **Read-Only Operations**: Listing platform businesses (`GET /api/v1/platform/businesses`) is a read-only query and is not audited to prevent log bloating.
