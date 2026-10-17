# ROMS Stage 3 — Business Ownership, Outlet Managers & Outlet-Scoped Subscriptions Architecture

> **Status:** Target Architecture Specification (Approved product decisions; implementation NOT started)
> **Date:** 2026-10-17
> **Scope of this document:** Consolidated Stage 3 target architecture for business ownership and membership, initial owner credentials, outlet-scoped subscriptions (including Trial and `free_qr`), Platform Operator read-only authorization, audit actions, database constraints, and reconciliation requirements.
> **Boundary notice:** This is an architecture document. Nothing here is implemented by virtue of being written. Migration `0015`, outlet-subscription write endpoints, ownership constraints, router changes, and all other `[Target]` items are planned only. No application code, tests, migrations, configuration, or database contents were modified by the creation of this document.

## Evidence base and label legend

Claims in this document carry explicit labels:

- **`[Shipped]`** — verified against current source (branch `main`, post-`18b4558` working tree; Alembic head `0014`).
- **`[Target]`** — approved Stage 3 design; not implemented.
- **`[Legacy-protected]`** — existing behavior deliberately retained for pre-existing data, with documented removal criteria.
- **`[Prerequisite]`** — must be resolved or executed before dependent implementation slices.
- **`[Open question]`** — requires explicit owner approval before implementation.

Primary evidence files inspected for the `[Shipped]` claims: `backend/app/api/deps.py`, `backend/app/api/v1/platform.py`, `backend/app/api/v1/auth.py`, `backend/app/modules/staff/models.py`, `backend/app/modules/staff/service.py`, `backend/app/modules/businesses/{models,schemas,platform_service}.py`, `backend/app/modules/subscriptions/{models,service}.py`, `backend/alembic/versions/0010_subscription_entitlements.py`, `packages/api-client/src/client.ts`, `packages/shared-types/src/platform.ts`, `apps/platform-admin/src/**`.

## Related documents

| Document | Relationship |
| :--- | :--- |
| `docs/architecture/roms_owner_decisions.md` | Decision log. Stage 3 product policy is recorded there as **Decision 002 (outlet-scoped subscriptions)**, **Decision 003 (ownership, membership, initial credentials)**, and **Decision 004 (Operator read-only scope)**, approved 2026-10-17. *(Appending those entries to the log file is a separate pending documentation task; the decisions themselves are approved.)* |
| `docs/architecture/UI_Platform_Admin_Guidance_Flow.md` (v2.0.0) | UI blueprint; its outlet-scoped subscription invariants (§3.2 items 1, 2, 4) and conflict-resolution table (§7) align with this document. Its business-onboarding workflow (§4.2/§6.1), automatic-trial wording (§3.2 item 3, §6.2), multi-owner table (§4.3), and Operator write access (§6.4) are superseded by Decisions 002–004. |
| `docs/architecture/platform-access-control-and-team-management.md` | Living platform access-control spec. Its §1 invariant “Subscriptions Remain Business-Level” and its Operator-as-menu-writer definition are superseded by Decisions 002 and 004. |
| `docs/architecture/roms_platform_admin_subscription_architecture.md` | Phase B entitlement spec. Lifecycle semantics (zero-day grace, cancellation semantics) remain authoritative; its `BusinessSubscription`-as-sole-authority framing and fail-closed-when-missing claim are qualified by this document’s legacy-compatibility sections. |
| `docs/architecture/platform_audit_logging.md` | Audit action inventory; extended by the action list in §8 of this document. |
| Stage 3 implementation plan (conversation record, 2026-10-17) | File-level change inventory and test slices. This document supersedes that plan where they conflict; the corrected migration scope in §9 of this document overrides the plan’s original S1 index proposal. |

---

## 1. Confirmed product decisions (register)

Approved by the ROMS owner on 2026-10-17. Summarized here; the owner-provided wording is authoritative in the decision log.

**Decision 002 — Outlet-scoped subscriptions (selected rules).** Each outlet has an independent subscription; different outlets in one business may have different plans and lifecycle states. Creating a business never creates a subscription or starts a trial. Creating an outlet requires a plan selection; the UI defaults to Trial, and the administrator may choose another available plan. Trial creates a persisted subscription with start date, expiry date, and audit history, with the existing 30-day duration preserved. A new outlet never inherits another outlet’s subscription. An outlet’s subscription is independently manageable from its Outlet Detail page; changing one outlet never modifies another. There is no business-level plan selection and no propagation to outlets. `free_qr` (Free QR Menu) is selectable as an explicit plan and must be representable as an active, non-expiring free subscription distinguishable from an expired paid subscription. No outlet-count enforcement this phase. Plan catalog CRUD remains read-only. Business/outlet operational status stays separate from subscription lifecycle status. Legacy fallback behavior must be documented; no silent paid-tier entitlements for missing subscriptions going forward.

**Decision 003 — Ownership, membership, and initial credentials.** Business creation requires business details and mandatory owner details. During business creation in the Platform Admin portal, the authorized platform administrator sets the initial password for the new business owner. The initial owner password must be handled securely: never logged, never included in audit metadata, never exposed in error messages. Initial-password and first-login behavior is documented from existing implementation evidence; no mandatory password-change-on-first-login flow is part of the approved design. Email-based password change, reset, or invitation flows are future scope. Manager credential flows are not assumed identical to owner creation beyond what existing implementation evidence and the approved design support. A business may be created with no outlet and no subscription. Each business has exactly one owner at a time; multiple managers are allowed; a manager may be assigned to one or multiple outlets of that business; outlet-manager assignment is optional. Add Outlet may support selecting the owner, an existing manager, or (where safely supported) provisioning a new manager. Existing business users are reused where appropriate — no duplicate accounts. The owner has access to every outlet of the business regardless of who is the outlet’s responsible manager; managers access only explicitly assigned outlets. Ownership transfer is explicit, atomic, and auditable; the previous owner is demoted to manager. A user may own multiple businesses; no global one-business-per-user restriction. Suspended or otherwise inactive users are rejected as owner/manager assignment targets until reactivated. Existing zero-owner businesses are report-only; any repair requires a separately approved task.

**Decision 004 — Platform Operator strict read-only scope.** Operators have strict read-only access to the approved Platform Admin pages (Overview, Businesses, business/outlet details, Subscriptions, Plans, Audit Logs). Operators must not mutate businesses, outlets, subscriptions, plans, ownership, platform team membership, or audit records. The existing platform-menu write exception is removed; menu-related Platform Admin access is also read-only. Read-only access is enforced by backend authorization, not merely frontend navigation. Team administration is unavailable to Operators. Route and data exposure contradicting this policy must be identified and corrected.

---

## 2. Identity, ownership, and membership model

### 2.1 Global user identity `[Shipped]`

`User` (`backend/app/modules/staff/models.py:13-32`) is a global identity: unique `email`, required `password_hash` (bcrypt via `hash_password`), `display_name`, `status` (`active` / `suspended` / other non-active values), plus platform-plane fields `is_platform_admin` and `platform_role`. Authentication is stateless JWT (`POST /auth/login`; `get_current_user` hydrates the user row per request and rejects `status != "active"` with 401 — `deps.py:36-37`). There is no password-reset, invitation, or first-login endpoint (`auth.py` is login + `/me` only).

Platform-plane roles (`platform_role`: `owner` / `admin` / `operator`) are decoupled from tenant roles and confer no implicit tenant membership `[Shipped, preserved]`.

### 2.2 Membership tables `[Shipped schema; Target semantics]

- **`BusinessMembership`** (`staff/models.py:60-81`): unique `(business_id, user_id)`; free-string `role` (default `"owner"`). **`[Shipped]`** No code path currently creates `role="manager"` rows; only seed data creates outlet-level managers. **`[Target]`** `BusinessMembership(role="owner")` is the canonical business-owner record; `BusinessMembership(role="manager")` rows represent managers associated with the business.
- **`OutletMembership`** (`staff/models.py:36-57`): unique `(user_id, outlet_id)` — one user may hold memberships across many outlets. Roles: `owner`, `manager`, `waiter`, `kitchen` `[Shipped]`.

### 2.3 Exactly-one-owner invariant `[Target]`

Guaranteed by three cooperating layers:

1. **Database:** partial unique index `uq_business_one_owner ON business_memberships (business_id) WHERE role = 'owner'` (planned migration `0015`; SQLite + PostgreSQL dialect variants, following the `0010:102-119` / `OutletSubscription` partial-index pattern). Not deployed.
2. **Service:** business-owner assignment/transfer executes demote-old (`role → "manager"`) and promote-new inside one transaction under `SELECT ... FOR UPDATE` on the `Business` row (pattern already shipped in `update_business_subscription:276-277` and `add_outlet_to_business:733-734`), serializing concurrent transfers; the partial unique index is the hard backstop against any double-owner commit.
3. **Creation path:** business creation writes the owner membership in the same transaction as the business row (§3), eliminating the current window for owner-less businesses on the happy path.

**`[Shipped]` Current gap:** `assign_owner_to_outlet` (`platform_service.py:818-910`) requires an `outlet_id`, never demotes a previous owner, and performs no uniqueness enforcement — zero-owner and multi-owner businesses are possible today. **`[Target]`** the outlet coupling is removed (§5.1) and transfer semantics above apply.

A user may own multiple businesses: no constraint prohibits this and Decision 003 forbids introducing one `[Target: preserved absence of constraint]`.

### 2.4 Owner access to all outlets `[Shipped; preserved]`

`RequireOutletRole` (`deps.py:141-189`) resolves access as: explicit `OutletMembership` first; otherwise, for users holding `BusinessMembership(role="owner")` on the outlet’s business, a synthesized owner membership (154-163, 185-189). Pinned by `test_outlet_subscriptions_phase1.py::test_business_owner_membership_synthesizes_outlet_access`. Business-wide owner access therefore requires no per-outlet rows.

**Hazard and rule `[Target]`:** because an existing membership row is evaluated *before* business-owner synthesis (178-184), storing `OutletMembership(role="manager")` for the business owner would narrow their access on owner-only routes. When the owner is selected as an outlet’s responsible person, the membership row must be stored with `role="owner"` (UI label: “Owner — full business access”), never `"manager"`. Managers receive `role="manager"` rows only on explicitly assigned outlets; manager access is strictly membership-scoped `[Shipped via RequireOutletRole; Target for the assignment write path]`.

### 2.5 Managers `[Target]`

- Associated with the business via `BusinessMembership(role="manager")` (multiple allowed; unique `(business_id, user_id)` prevents duplicates).
- Assigned to one or more outlets via `OutletMembership(role="manager")` rows; assignment optional at outlet creation.
- Add Outlet selector options: the business owner; an existing business manager; or a newly provisioned manager where safely supported. Existing users are resolved by `user_id` and never duplicated; new users follow the same dual-mode contract shipped for owner assignment and operator onboarding (`user_id` xor `email + password + display_name`, mutual-exclusion validated — `schemas.py:159-181` pattern). `[Target, grounded in Shipped patterns]` Manager provisioning is **not** asserted to be byte-identical to owner creation; differences (business-scoped manager validation, membership writes, audit action) are specified in the Stage 3 implementation plan.
- **`[Target]`** Suspended or otherwise inactive users are rejected as owner or manager assignment targets (validation in assignment/transfer services). **`[Shipped]`** no such validation exists today (`assign_owner_to_outlet` assigns any user id).

### 2.6 Ownership transfer `[Target]`

Explicit API operation (not a side effect of re-running assign): one transaction — lock business row; demote current owner’s `BusinessMembership` to `"manager"` (retaining their outlet memberships, which continue to grant access via explicit rows); promote target (creating user if the new-user mode is used); write audit `platform.business_owner.transfer` with before/after actor ids; commit. Failure at any point rolls back all membership changes. Partial unique index guarantees single-owner even under races.

### 2.7 Duplicate-user prevention `[Shipped mechanism; Target discipline]`

`users.email` is globally unique; assignment flows look up by `user_id` or lowercased email before creating (`platform_service.py:839-858` pattern) and set `created_new_user` in audit metadata. Stage 3 reuses this discipline everywhere; no flow may create a second account for an existing email.

---

## 3. Initial owner credentials `[Shipped pattern; Target scope]`

**Approved design (Decision 003):** during business creation in the Platform Admin portal, the authorized platform administrator (Owner/Admin) sets the initial password for the new business owner, together with the owner’s email and display name, when the owner is a new user. This extends the shipped provisioning pattern (`assign_owner_to_outlet` 843-858; `create_platform_operator` 1218) to the business-creation transaction.

**First-login behavior — documented from evidence, not invented:** the current implementation has **no** mandatory password-change-on-first-login flow. There is no `must_change_password` flag, no `password_changed_at` column, no password-change endpoint, and JWTs are stateless with 7-day expiry and no revocation table (`phase_1e_support_tools_security_design.md` verified this). Decision 003 does not introduce a forced-change flow in this phase. The created owner logs in with the administrator-set password like any existing user. Changing the password post-login is not currently an endpoint and is not part of Stage 3 scope.

**Security requirements `[Target, enforceable now]`:**

- The initial password travels only in the HTTPS request body of the provisioning call and is stored exclusively as a bcrypt hash in `users.password_hash`.
- Plaintext passwords must never appear in application logs, audit `metadata_json`, API responses after the creating call returns, or error messages. Audit records capture only `assigned_user_id` / `created_user_id`, `email`, role, and `created_new_user` flags (pattern already enforced — `platform_audit_logging.md` §5; `platform.owner.assign` metadata at `platform_service.py:899-905`).
- Provisioning endpoints remain Owner/Admin-only (operations router), so only authorized platform administrators can set initial credentials.

**Out of scope, explicitly:** email invitations, email delivery, password-reset flows, expiring tokens, and any alternative credential-delivery mechanism. These are future scope and must not be designed or implemented under Stage 3.

---

## 4. Business and outlet lifecycle workflows `[Target]`

### 4.1 Create business with owner (no outlet, no subscription)

One transaction: resolve or create owner `User` (admin-set password; flush) → `Business(status="active")` with legacy subscription columns left null → `BusinessMembership(role="owner")` → audit `platform.business.create` (metadata: business name, owner user id, `created_new_user` — **no** password, no outlet/subscription fields) → commit. On any failure, full rollback; no orphan business, no orphan user beyond the unique-email guard. Owner assignment no longer requires an outlet to exist.

### 4.2 Transfer ownership

Per §2.6. Explicit endpoint; atomic; audited as `platform.business_owner.transfer`.

### 4.3 Add outlet (required plan, Trial default, optional manager)

Single transaction under business-row lock: slug uniqueness check → create `Outlet` → create `OutletSubscription` from the selected `plan_code` (see §6) → resolve optional manager (owner → `role="owner"` row; existing business manager → `role="manager"` row; new manager → user + business-manager + outlet-manager rows; suspended/inactive targets rejected) → copy existing business owners onto the new outlet as `role="owner"` rows (shipped behavior `783-794`, retained) → audit `platform.outlet.create` (now including `plan_code`, manager ids) → commit. Any failure rolls back outlet, subscription, and memberships together — no orphan outlet, no half-assigned manager.

### 4.4 Manage outlet subscription

From the Outlet Detail page only: lifecycle actions (activate/renew/change plan/extend trial/cancel/past-due family) apply to that outlet’s `OutletSubscription` via atomic row swap (`is_current → False` on the old row; insert new current row), under per-outlet locking, with full before/after audit. Sibling outlets’ subscriptions are never touched. Business-level plan management does not exist.

### 4.5 Suspend / reactivate business

Operational status (`Business.status ∈ {active, suspended}`) changes via the business profile PATCH (`[Target]` — status field added there), independently of any subscription lifecycle; audit `platform.business.suspend` / `platform.business.reactivate` (action names preserved from shipped `696-698`). Suspension remains the hard kill switch checked before entitlements (`EntitlementService._evaluate_feature_entitlement:110-118`; `RequireOutletRole:171-176`) `[Shipped; preserved]`.

---

## 5. Platform API contracts affected `[Target, summary level]`

Contract detail lives in the Stage 3 implementation plan; architecture-level changes:

| Area | Change |
| :--- | :--- |
| `POST /platform/businesses` | Requires `owner {email, password, display_name}` (new-user mode) or `owner {user_id}` (existing-user mode). Removes `primary_outlet_name`, `public_slug`, `currency`, `timezone`, `subscription_status`, `plan_name`, `max_outlets`, `trial_ends_at`. Single consumer confirmed: `packages/api-client` `createPlatformBusiness` ← platform-admin only. |
| `POST /platform/businesses/{id}/assign-owner` | Becomes business-scoped owner assign/transfer; `outlet_id` removed from the payload. |
| `POST /platform/businesses/{id}/outlets` | Adds required `plan_code` (`trial` sentinel or a canonical plan code) and optional `manager` block (dual-mode). |
| `GET /platform/outlets/{id}/subscriptions`, `PATCH /platform/outlets/{id}/subscription` | New; outlet-scoped history read and lifecycle writes. |
| `PATCH /platform/businesses/{id}` | Gains optional operational `status`. |
| `PATCH /platform/businesses/{id}/subscription` | Removed (single consumer: `updatePlatformSubscription` in `client.ts` ← `SubscriptionEditModal` only). Operational status split lands first. |
| `PATCH /platform/outlets/{id}` | Moves from `profile_router` to owner/admin router (Operator mutation hole, §7). |

Affected Platform Admin pages: Business Directory (create flow), Business Detail (owner transfer, add-outlet form, owner section becomes single-owner), Outlet Detail (subscription tab becomes writable), Subscriptions Overview (per-outlet rows), Team (unchanged, owner/admin only), Audit Logs, Operator navigation (filtered, read-only).

---

## 6. Subscription and entitlement architecture

### 6.1 Outlet-scoped authority `[Target over Shipped dual model]`

`OutletSubscription` (`subscriptions/models.py:76-108`) is the canonical subscription record per outlet, with a deployed partial unique index `uq_outlet_subscription_current` (one current row per outlet) `[Shipped]`. The entitlement resolver already checks the outlet’s current subscription first (`service.py:394-406`) and honors per-outlet plan independence (tests: `test_outlet_a_sub_does_not_affect_outlet_b`, `test_different_plans_per_outlet_resolved_independently`) `[Shipped]`.

What is **not** shipped: outlet-level subscription write endpoints, plan selection at outlet creation, and removal of business-level propagation. The shipped business-level `PATCH /platform/businesses/{id}/subscription` ends in `_propagate_subscription_to_outlets` (`platform_service.py:680`, def 239-266), which overwrites every current outlet subscription’s plan and lifecycle fields — the single largest conflict with Decision 002. `[Shipped hazard; Target: deleted.]`

### 6.2 Trial `[Shipped duration; Target selection semantics]`

30-day trial duration is preserved (Decision 002; no material issue found — today hardcoded `timedelta(days=30)` at 147 and 769; `[Target]` extract to a single `TRIAL_DURATION_DAYS` constant without behavior change). Trial expiry semantics: 0-day grace, `now >= trial_ends_at` → expired (`evaluate_subscription_status:76-82`) `[Shipped; authoritative]`.

**`[Target]`** Trial is the UI default selection on Add Outlet, not an automatic side effect: choosing Trial persists `OutletSubscription(status="trial", trial_ends_at = now + 30d)` with audit. Choosing any other active plan persists an `active` subscription for that plan instead. No silent default plan. A new outlet under a paid business still defaults to Trial in the UI; the administrator may pick another plan; inheritance of a sibling’s subscription never occurs.

### 6.3 Free QR Menu (`free_qr`) `[Shipped catalog; Target lifecycle semantics]`

`free_qr` is seeded (`0010:139`, features at 181-182: `menu.digital` + `outlets.max_count = 1`) and returned by the read-only plans API `[Shipped]`. Decision 002 requires it selectable as an explicit plan, represented as an active, non-expiring free subscription.

**Conflict to resolve at implementation `[Target design]`:** the resolver fail-closes `active` + `current_period_end = NULL` to `"expired"` (`service.py:89-90`), which would display Free as expired (functionally it would still serve `menu.digital` via the read-only fallback, §6.5). The approved approach: special-case free-tier plans in `evaluate_subscription_status` (keyed on `plan.code == "free_qr"` for now — no schema change) so an `active` free subscription resolves `"active"` regardless of period. Row-swap history works unchanged for free rows. No code path auto-creates Free subscriptions; administrators select it explicitly.

### 6.4 Lifecycle actions, history, concurrency `[Target; grounded in Shipped mechanisms]`

Outlet subscription mutations reuse the shipped dispatcher semantics (strict 1-calendar-year annual terms, action families activate/renew/change_plan/extend_trial/cancellations/past-due — `platform_service.py:322-598`) with atomic row swap for history preservation (pattern pinned by `test_trial_conversion_starts_immediately_and_retains_history`), serialized by `FOR UPDATE` on the Outlet row, with `uq_outlet_subscription_current` as the database backstop. Audit: `platform.outlet_subscription.create` / `platform.outlet_subscription.update` with before/after images.

### 6.5 Legacy compatibility `[Legacy-protected]`

**Shipped fallback chain** (`service.py:408-476`): no outlet subscription → business current `BusinessSubscription` → legacy `Business` columns, where missing rows default `subscription_status or "active"` and synthesize a plan from `plan_name` (fallback `growth_pos`/`starter_pos`). This can currently grant paid-tier entitlements to entities without any subscription row — the behavior Decision 002 forbids going forward.

**Stage 3 stance:**

- New writes never create business-level subscriptions or legacy-column values; business creation leaves them null; every new outlet gets an outlet subscription row.
- Fallbacks remain only for the pre-existing cohort (legacy businesses/outlets) so production behavior does not regress during rollout. `READ_ONLY_MENU_ALLOWED` for expired/cancelled states (`service.py:120-130`) is preserved untouched as the safety net.
- **Removal criteria (future slice, not Stage 3):** read-only reconciliation report (§9) shows (i) zero outlets without a current outlet subscription and (ii) zero businesses with current business-level subscriptions; only then may the business-sub and legacy-column fallbacks be deleted, in a dedicated change with its own tests.
- `outlets.max_count` / `Business.max_outlets`: no enforcement this phase (Decision 002). The entitlement resolver may keep reading the legacy scalar for display; `add_outlet_to_business` performs no capacity check (its shipped docstring claiming otherwise is inaccurate `[Shipped]`).

### 6.6 Operational vs. subscription status `[Shipped separation; preserved]`

`Business.status` / `Outlet.status` (operational) are distinct from subscription `status` (`trial`/`active`/`past_due`/`cancelled`, resolved `expired`). No code path mutates subscription rows when operational status changes; Stage 3 preserves this by splitting operational status onto the business profile PATCH and deleting the combined endpoint.

---

## 7. Platform authorization `[Target; correcting Shipped gaps]`

### 7.1 Target role matrix (Platform plane)

| Capability | Owner | Admin | Operator |
| :--- | :---: | :---: | :---: |
| Overview data (`GET /platform/businesses` profile-shape, `GET /audit-logs`) | RW | RW | **Read** `[Target: new]` |
| Businesses list/detail, outlet detail (GET) | RW | RW | Read (detail reads already allowed `[Shipped]`; list/audit/plans reads currently 403 for operators `[Shipped gap]`) |
| Create business, transfer owner, add outlet, manager assignment | RW | RW | ❌ |
| Business/outlet profile PATCH (incl. operational status) | RW | RW | ❌ (`PATCH /platform/outlets/{id}` currently allowed for operators via `profile_router` — `platform.py:237-241, 605-617` `[Shipped hole; Target: moved to owner/admin router]`) |
| Outlet subscription GET / PATCH (new) | RW | RW | Read / ❌ |
| Business-subscription PATCH | ~~removed~~ (§6.1) | | |
| Entitlements & overrides (GET) | RW | RW | Read (optional, see open questions) |
| Entitlements & overrides (writes) | RW | RW | ❌ |
| Plans (GET, read-only catalog) | Read | Read | **Read** `[Target: new]` |
| Team (admins/operators CRUD, platform owner transfer, suspend/reactivate) | RW | — (existing owner-only protections preserved `[Shipped]`) | ❌ |
| Platform menu (GET) | RW | RW | Read |
| Platform menu (POST/PATCH/DELETE) | RW | RW | **❌ `[Target]` — write exception removed (Decision 004)**; currently operator-writable (`platform_menu.py:26`, policy table 158-191, `test_platform_operator_menu.py`) `[Shipped]` |

Enforcement is always backend router dependencies (`RequirePlatformRole` per sub-router: governance {owner}, commercial/operations {owner, admin}, profile {owner, admin, operator} today `[Shipped]`; a new read-oriented commercial-read grouping carries the operator reads). Frontend navigation filtering in `PlatformShell` is UX only; direct links are stopped by 403s from router deps. The `PLATFORM_ROUTE_POLICIES` table (`platform.py:60-213`) must be updated in lockstep and pinned by a fixture test.

Business Portal roles (owner/manager/waiter/kitchen via `RequireOutletRole`) are unchanged and out of Stage 3 scope except as noted in §2.4-2.5.

### 7.2 Operator data exposure `[Target]`

Operator-visible audit rows are limited to the **minimum necessary fields**: `id`, `action`, `entity_type`, `entity_id`, `business_id`, `outlet_id`, `created_at`, `actor_display_name`, and business/outlet names — **excluding** `actor_email` and free-form `metadata_json` (which may contain owner emails and provisioning context). Owner/Admin retain the full serialization. This redaction is a `[Target]` serializer concern; platform audit reads remain platform-role-only and are never exposed on tenant endpoints `[Shipped; preserved]`.

### 7.3 Alternate-write-path check for menu removal `[Shipped verification]`

Platform menu writes exist only on `platform_menu_router`; tenant menu routes require `RequireOutletRole` memberships, and platform roles grant no implicit tenant membership (`deps.py` boundary; access-control spec invariant). Removing the operator exception on the platform router leaves no alternate platform write path. Dual-hatted users (a person who separately holds tenant memberships) retain legitimate tenant-side access; that is not a platform bypass.

---

## 8. Audit actions `[Shipped inventory; Target additions]`

Current shipped platform action names (verified in `platform_service.py` / `subscriptions/service.py`): `platform.business.create`, `platform.business.profile_update`, `platform.business.update_subscription` (generic) plus dispatcher family `platform.subscription.{update,activate,renew,change_plan,change_plan_new_term,extend_trial,schedule_cancellation,revoke_scheduled_cancellation,cancel_immediately,mark_past_due,mark_past_due_with_extension}`, `platform.business.{suspend,reactivate}`, `platform.outlet.create`, `platform.outlet.profile_update`, `platform.owner.assign`, `platform.owner.transfer` (**platform-team** transfer — distinct from business ownership), `platform.admin.{grant,revoke}`, `platform.operator.{create,revoke}`, `platform.user.{suspend,reactivate}`, `platform.entitlement.override_{create,revoke}`.

**`[Target]` Stage 3 additions/changes:**

| Action | Notes |
| :--- | :--- |
| `platform.business_owner.transfer` | New; business ownership transfer (demote-to-manager semantics). Must not reuse `platform.owner.transfer` (platform-plane). |
| `platform.outlet_subscription.create` | Outlet creation with explicit subscription. |
| `platform.outlet_subscription.update` | Outlet-scoped lifecycle change; before/after images. |
| `platform.business.create` metadata change | Drops primary-outlet/plan fields; adds owner user id + `created_new_user`. |
| `platform.outlet.create` metadata change | Adds `plan_code`, manager ids. |
| `platform.owner.assign` | Retired with the outlet-coupled endpoint (replaced by transfer/assign without `outlet_id`; action name for the business-scoped assign path is specified in the implementation plan). |

Password handling rules remain as shipped and are restated for Stage 3: no passwords, hashes, or tokens in audit metadata or logs (`platform_audit_logging.md` §5).

---

## 9. Database constraints, migration, and reconciliation

### 9.1 Constraints

| Constraint | Status | Guarantee |
| :--- | :--- | :--- |
| `uq_outlet_subscription_current` (partial unique, `outlet_id` WHERE `is_current`) | **`[Shipped]`** (`subscriptions/models.py:78-85`) | At most one current subscription per outlet |
| `uq_business_current_subscription` (partial unique, `business_id` WHERE `is_current`) | **`[Shipped]`** — created by migration `0010:102-119` (both dialects). **`[Gap]`** the ORM model does not declare it in `__table_args__` (`models.py:55-73`), so SQLite test databases built via `Base.metadata.create_all` do not enforce it | At most one current business-level subscription row (legacy cohort) |
| `uq_business_one_owner` (partial unique, `business_id` WHERE `role='owner'`) | **`[Target]`** — does not exist | At most one owner membership per business |
| `uq_user_outlet_membership`, `uq_business_user_membership` | `[Shipped]` | No duplicate membership rows |

### 9.2 Migration plan (corrected) `[Target]`

**Planned migration `0015` adds only:**

1. `uq_business_one_owner` partial unique index on `business_memberships (business_id) WHERE role = 'owner'` (dialect-conditional, per the `0010` pattern), mirrored by an ORM `__table_args__` declaration so test databases enforce the same rule.
2. ORM metadata parity only (no database DDL) for `uq_business_current_subscription`: declare the already-deployed index on `BusinessSubscription.__table_args__` so SQLite test DBs enforce it.

`0015` does **not** recreate `uq_business_current_subscription` (it exists), does not backfill data, does not repair owners, and does not alter subscription rows. Downgrade drops only the new index.

**Migration preconditions `[Prerequisite]`:**

- Read-only reconciliation report (§9.3) run against the target database; the upgrade must abort if any business has two or more owner rows (same abort pattern as migration `0012`’s multiple-owner precheck, `test_alembic_migrations.py:266`). Zero-owner businesses do not block the index.
- Dialect verification on staging PostgreSQL (transactional DDL rollback expectation, per the standing migration policy in `roms_platform_admin_subscription_architecture.md` §9).

### 9.3 Read-only reconciliation report `[Target tool; report-only per Decision 003]`

A SELECT-only script/ops run producing, at minimum:

1. **Zero-owner businesses** — id, name, created_at. **Report-only; no automatic repair. Any repair is a separately approved task.**
2. **Multiple-owner businesses** — must be empty before `0015` applies; listing id + all owner user ids.
3. **Outlets without a current `OutletSubscription`** — candidates for the legacy fallback cohort.
4. **Businesses with current `BusinessSubscription` rows** — legacy cohort consuming fallbacks (§6.5).
5. **Denormalized drift** — `businesses.subscription_status` / `plan_name` / `max_outlets` / `trial_ends_at` versus the current business-subscription row, where both exist.

No writes, no PII beyond business/outlet identifiers and display names already present in platform UIs.

### 9.4 Rollback `[Target]`

Code slices are independently revertible; `0015` downgrade drops only `uq_business_one_owner`; no destructive data migration exists to reverse. Audit events are append-only and roll back with their transaction on failure `[Shipped pattern]`.

---

## 10. Current versus target summary

| Concern | Current `[Shipped]` | Target `[Target]` |
| :--- | :--- | :--- |
| Business create | Outlet + trial subscriptions required/auto; owner assigned later via outlet-coupled endpoint | Owner mandatory in-txn; no outlet; no subscription; no trial |
| Owner uniqueness | Unenforced (0 or 2+ possible) | Partial unique index + transfer-under-lock |
| Owner all outlets | Synthesis works | Preserved; owner-as-responsible stores `role="owner"` |
| Managers | No business-manager API; outlet rows only (seed) | Business + outlet manager model; optional at outlet create; reuse users |
| Owner credentials | Admin-set password (assign-owner/operator patterns) | Same pattern moved into business create; password never logged/audited/echoed |
| First-login change / email reset | Do not exist | Not designed in Stage 3; email flows future scope |
| Suspended-user assignment | Allowed (no check) | Rejected until reactivated |
| Outlet create | Forced `starter_pos` trial; no plan/manager params | Required plan (Trial default); optional manager |
| Outlet sub management | None (UI states API missing) | Per-outlet GET/PATCH + row-swap history |
| Business sub PATCH + propagation | Overwrites all outlet subs | Deleted; operational status split to profile PATCH |
| `free_qr` lifecycle | Active+no-period resolves expired | Free-tier non-expiring resolution |
| No-sub fallback | Can yield active + synthesized paid plan | Legacy-protected; frozen; removal criteria defined |
| Operator | Reads blocked on list/plans/audit; writes allowed on outlet PATCH + menus | Full approved read set; zero writes; redacted audit fields |
| Audit docs | 6 actions documented | Full inventory + Stage 3 actions incl. `platform.business_owner.transfer` |

---

## 11. Prerequisites and open questions

**Prerequisites before the corresponding implementation slices `[Prerequisite]`:**

1. Record Decisions 002-004 in `docs/architecture/roms_owner_decisions.md` (approved content; append task pending).
2. Amend the Stage 3 implementation plan S1 to match §9.2 (owner index only; ORM parity; no recreation of the deployed business-subscription index).
3. Align `UI_Platform_Admin_Guidance_Flow.md`, `platform-access-control-and-team-management.md`, and `platform_audit_logging.md` with this document (separate approved documentation tasks).

**Open questions `[Open question]` (none block the document itself):**

1. Operator read of entitlements/overrides inspection endpoints: include (useful for support) or exclude? Default proposal: read-only included.
2. Business-scoped owner assign (non-transfer, first assignment when an owner already exists should be impossible post-invariant — confirm transfer is the only post-creation write).
3. Whether `Subscriptions Overview` for operators hides legacy business-level columns (recommended) or mirrors the owner/admin view.
4. Exact serializer field list for the redacted operator audit view (§7.2 proposes one; needs sign-off at implementation).

---

*End of Stage 3 architecture specification. Implementation remains unauthorized until the owner approves the corresponding implementation plan slices.*
