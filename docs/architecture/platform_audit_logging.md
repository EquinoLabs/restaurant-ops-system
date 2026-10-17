# Platform Audit Logging Architecture

> **Stage 3 alignment note (2026-10-17):** §2 now distinguishes **[Shipped]** actions (verified in code) from **[Target]** planned additions (Owner Decisions 002–004; not implemented). §5 strengthens the secret-exclusion rules. §6 documents planned minimum-necessary Operator visibility with redaction. Authoritative reference: `docs/architecture/stage_3_ownership_subscriptions_architecture.md` §8.

## 1. Overview

ROMS (Restaurant Operations Management System) records audit logs for administrative actions taken by platform administrators. Audit entries are persisted to the central `audit_logs` table.

---

## 2. Audited Operations & Action Naming Conventions

All platform audit actions use the `platform.<domain>.<verb>` naming scheme.

### 2.1 Business & Ownership Actions

| Operation | Action Identifier | Status | Entity Type | Target Business ID | Target Outlet ID | Description & Metadata Captured |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Business Creation** | `platform.business.create` | `[Shipped]` | `business` | `business.id` | primary outlet, if any | Records provisioning of a business. `[Shipped]` Currently also records the auto-created primary outlet and plan/subscription metadata; Stage 3 removes automatic outlet/subscription creation. Owner password is **never** included. |
| **Business Profile Update** | `platform.business.profile_update` | `[Shipped]` | `business` | `business.id` | `None` | Records business metadata edits. Before/after snapshots. |
| **Business Suspension** | `platform.business.suspend` | `[Shipped]` | `business` | `business.id` | `None` | Operational status → `"suspended"`. Before/after snapshots. |
| **Business Reactivation** | `platform.business.reactivate` | `[Shipped]` | `business` | `business.id` | `None` | Operational status → `"active"`. Before/after snapshots. |
| **Business Ownership Transfer** | `platform.business_owner.transfer` | `[Target]` | `membership` | `business.id` | `None` | Stage 3: explicit, atomic business ownership transfer; previous owner demoted to manager. Records previous/new owner user IDs and role changes. **Distinct from `platform.owner.transfer` (platform-plane).** |
| **Business Manager Assign** | `platform.business_manager.assign` | `[Target]` | `membership` | `business.id` | assigned outlet IDs, if any | Stage 3: manager assignment to a business and optional outlets. Records assigned user ID, email, created-new-user flag. No credentials. |
| **Business Manager Revoke** | `platform.business_manager.revoke` | `[Target]` | `membership` | `business.id` | `None` | Stage 3: manager revocation. Records revoked user ID and role. |

### 2.2 Outlet & Subscription Actions

| Operation | Action Identifier | Status | Entity Type | Target Business ID | Target Outlet ID | Description & Metadata Captured |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Outlet Creation** | `platform.outlet.create` | `[Shipped]` | `outlet` | `business.id` | `outlet.id` | Records outlet creation. Includes name, public slug, currency, timezone. `[Shipped]` Currently auto-creates a forced `starter_pos` trial; Stage 3 requires explicit plan selection (Trial default). |
| **Outlet Profile Update** | `platform.outlet.profile_update` | `[Shipped]` | `outlet` | `business.id` | `outlet.id` | Records outlet metadata edits. Before/after snapshots. |
| **Business Subscription Update (legacy)** | `platform.business.update_subscription` | `[Shipped; legacy]` | `business` | `business.id` | `None` | Business-level subscription mutation with propagation to all outlet subscriptions. Stage 3 removes this path and its propagation; retained here for history. |
| **Subscription Lifecycle Actions** | `platform.subscription.update`, `.activate`, `.renew`, `.change_plan`, `.change_plan_new_term`, `.cancel_immediately`, `.schedule_cancellation`, `.revoke_scheduled_cancellation`, `.mark_past_due`, `.mark_past_due_with_extension`, `.extend_trial` | `[Shipped]` | `subscription` | `business.id` | `outlet.id` | Outlet-subscription lifecycle mutations with before/after snapshots. |
| **Subscription Create (explicit)** | `platform.subscription.create` | `[Target]` | `subscription` | `business.id` | `outlet.id` | Stage 3: explicit subscription record created at outlet creation (Trial default or selected plan). |

### 2.3 Platform Team & User Governance Actions

| Operation | Action Identifier | Status | Entity Type | Target Business ID | Target Outlet ID | Description & Metadata Captured |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Owner Assignment (outlet-scoped)** | `platform.owner.assign` | `[Shipped]` | `membership` | `business.id` | `outlet.id` | Records assignment of an owner user for an outlet. Includes assigned user ID, email, role, `created_new_user` flag. No credentials. |
| **Platform Ownership Transfer** | `platform.owner.transfer` | `[Shipped]` | `platform_user` | `None` | `None` | **Platform-plane** owner transfer ceremony. Never conflated with `platform.business_owner.transfer`. |
| **Admin Grant/Revoke** | `platform.admin.grant`, `platform.admin.revoke` | `[Shipped]` | `platform_user` | `None` | `None` | Platform admin privilege grant/revoke with last-admin protection. |
| **Operator Create/Revoke** | `platform.operator.create`, `platform.operator.revoke` | `[Shipped]` | `platform_user` | `None` | `None` | Platform operator provisioning and revocation. |
| **User Suspend/Reactivate** | `platform.user.suspend`, `platform.user.reactivate` | `[Shipped]` | `user` | `None` | `None` | Account status transitions. |

### 2.4 Platform Menu Actions

| Operation | Action Identifier | Status | Entity Type | Target Business ID | Target Outlet ID | Description & Metadata Captured |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Menu Category Create/Update** | `platform.outlet.menu_category.create`, `platform.outlet.menu_category.update` | `[Shipped]` | `menu` | `business.id` | `outlet.id` | Menu category mutations via dedicated platform routes. |
| **Menu Item Create/Update** | `platform.outlet.menu_item.create`, `platform.outlet.menu_item.update`, `platform.outlet.menu_item.availability`, `platform.outlet.menu_item.image_upload`, `platform.outlet.menu_item.image_delete` | `[Shipped]` | `menu` | `business.id` | `outlet.id` | Menu item mutations via dedicated platform routes. `[Stage 3 note]` Under Owner Decision 004 these mutating routes become Admin/Owner-only; Operators retain read-only access and do not generate these events. |

> **Naming rule:** Business ownership transfer is `platform.business_owner.transfer`. Platform-plane ownership transfer is `platform.owner.transfer`. The two are never interchanged.

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

The following sensitive fields are **strictly prohibited** from appearing in audit `metadata_json` or any audit fields (this prohibition applies to every action, including the `[Target]` Stage 3 actions in §2):

- Passwords, initial passwords, temporary passwords, and raw authentication credentials.
- Password hashes (`password_hash`).
- Access tokens, refresh tokens, JWTs, invitation/reset tokens.
- R2 credentials, API keys, database connection strings.

This prohibition covers `metadata_json`, action parameters, error messages raised alongside audit emission, and any before/after state snapshots. When a new owner user is created via `platform.owner.assign` (or via Stage 3 business creation), the user's password is hashed and stored in `users`, but the audit payload records only `assigned_user_id`, `email`, `role`, and `created_new_user`.

---

## 6. Access Control & Tenant Isolation

- Platform audit operations require active-platform-administrator authentication (historically `get_current_platform_admin`; current platform-plane routers enforce `RequirePlatformRole`).
- Ordinary business admins and staff users cannot trigger platform audit events.
- Platform audit logs are not exposed to tenant business users or staff via standard outlet endpoints (`/outlets/{id}/audit-logs` returns only outlet-scoped menu audit events).
- **Operator Read Access & Redaction `[Target — Owner Decision 004, not implemented]`:** Platform Operators may read platform audit logs through a dedicated **redacted serializer** exposing only the minimum fields necessary for support: `id`, `action`, `entity_type`, `entity_id`, `business_id`, `outlet_id`, `actor_user_id`, `created_at`, and a coarse outcome field. The following are **redacted** from Operator responses: `actor` email/display name, free-form `metadata_json` payloads (which may contain before/after snapshots of tenant data), and any fields beyond the minimum set. Owner/Admin responses may include the fuller record set (excluding the §5 prohibited secrets, which are never stored at all). Backend serialization enforces the redaction; frontend filtering alone is insufficient.

---

## 7. Current Limitations

- **Failed Request Auditing**: Unauthenticated requests or invalid request payloads (400/401/403/422 validation failures) fail before reaching service execution and are not persisted as audit entries in the database.
- **Read-Only Operations**: Listing platform businesses (`GET /api/v1/platform/businesses`) is a read-only query and is not audited to prevent log bloating.
