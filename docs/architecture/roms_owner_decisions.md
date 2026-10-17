# ROMS Owner Decisions

**Purpose:** Record explicit product and business-policy decisions approved by the ROMS owner. These decisions guide implementation and resolve ambiguities in architecture documents.

## Decision Status

- **Proposed:** Awaiting owner approval.
- **Approved:** Explicitly approved by the owner.
- **Superseded:** Replaced by a later decision.

---

## Decision 001: Grant Scope Precedence

**Status:** Approved  
**Area:** Subscription Entitlements  
**Date:** 2026-10-11  

### Context

ROMS supports entitlement grants and restrictions at both business and outlet scope. The resolver needs deterministic rules when multiple overrides apply to the same feature.

### Decision

Option A — Hierarchical Scope Replacement

For a given target outlet and feature:

1. If one or more applicable active outlet-scoped grants exist, resolve grants using the outlet scope only.
2. Otherwise, resolve grants using applicable business-scoped grants.
3. When multiple numeric grants exist at the selected scope, use the highest numeric limit.
4. A grant with `limit_value = NULL` grants the capability but does not independently establish an unlimited numeric limit. If the selected scope has only null-limit grants, resolve the numeric limit through the documented plan, legacy restriction, and fallback rules.
5. An active restriction at either business or outlet scope overrides grants and denies the feature.
6. An outlet-scoped grant does not automatically increase the business-wide `outlets.max_count` creation allowance. Outlet-specific access and business-wide outlet creation capacity must be resolved separately.

### Related Policy

An outlet-scoped grant must not automatically increase the business-wide `outlets.max_count` creation limit. The implementation must distinguish granting access to a particular outlet from authorizing the creation of additional outlets.

### Implementation References

- `docs/architecture/roms_platform_admin_subscription_architecture.md`
- `docs/architecture/roms_platform_admin_implementation_roadmap.md`

### Approval Record

- Approved by: ROMS Owner  
- Approval date: 2026-10-11  
- Notes: Authorizes implementation of the documented precedence policy within Phase B. Does not authorize production migrations, deployment, or unrelated scope expansion.

---

## Decision 002: Outlet-Scoped Subscriptions

**Status:** Approved  
**Area:** Subscriptions & Entitlements  
**Date:** 2026-10-17  

### Context

Stage 3 architecture review confirmed that the commercial model is outlet-centric: businesses are containers for outlets, and each outlet runs its own commercial lifecycle. The shipped code already resolves entitlements from `OutletSubscription` first, but provisioning and mutation paths remain business-centric (auto-created primary outlet and trials, business-level subscription PATCH with propagation to all outlet subscriptions).

### Decision

1. Every outlet has its own independent subscription. Different outlets in the same business may use different plans and lifecycle states.
2. Creating a business must not automatically create an outlet, a subscription, or start a trial.
3. Creating an outlet requires plan selection. Trial is the default selection in the administrator UI; an authorized administrator may select another available plan before creation. Selecting Trial persists an explicit subscription with start date, expiry date, and audit history.
4. The existing 30-day trial duration is preserved; any change requires separate owner approval.
5. A new outlet does not inherit another outlet's subscription, including under businesses with existing paid outlets.
6. Subscription management is outlet-specific. Creating or changing one outlet's subscription must never modify any other outlet's subscription.
7. Business-level plan selection and propagation of business-level subscription changes to outlets are not part of the product.
8. The existing `free_qr` plan code provides the Free QR Menu. It must be selectable as an explicit plan and representable as an active, non-expiring free subscription, distinguishable from an expired paid subscription. No schema flag or schema change is approved for this; free-tier semantics are handled in the entitlement resolver's status evaluation.
9. No silent paid-tier entitlements are granted when a new outlet lacks a valid subscription. Existing subscription fallback behavior for pre-existing data is retained as legacy compatibility only, documented with removal criteria.
10. No outlet-count enforcement is introduced in this phase. Plan catalog CRUD remains read-only and out of scope.
11. Business/outlet operational status (`active`/`suspended`) remains separate from subscription lifecycle status.

### Related Policy

- Authoritative target architecture: `docs/architecture/stage_3_ownership_subscriptions_architecture.md`.
- Supersedes the business-level subscription scoping invariant in `docs/architecture/platform-access-control-and-team-management.md` §1 and the `BusinessSubscription`-as-sole-authority framing in `docs/architecture/roms_platform_admin_subscription_architecture.md` §7. Supersedes the automatic primary-outlet and automatic-trial onboarding flows in `docs/architecture/UI_Platform_Admin_Guidance_Flow.md` §4.2/§6.1/§6.2.

### Approval Record

- Approved by: ROMS Owner  
- Approval date: 2026-10-17  
- Notes: Product-policy approval for the Stage 3 documentation set. Does not by itself authorize implementation, migrations, or deployment; implementation requires separate approval of the Stage 3 implementation plan.

---

## Decision 003: Ownership, Membership, and Initial Owner Password

**Status:** Approved  
**Area:** Business Ownership & Identity  
**Date:** 2026-10-17  

### Context

Business ownership is currently coupled to outlet assignment (`POST /platform/businesses/{id}/assign-owner` requires an `outlet_id`), owner uniqueness is not enforced, no business-manager provisioning path exists, and owner credentials follow an ad-hoc admin-supplied-password pattern. Stage 3 formalizes the ownership model and the initial owner-password flow. This decision supersedes earlier draft wording about temporary generated credentials and mandatory first-login password change for business-owner creation; no such forced-change flow is part of the approved design.

### Decision

1. Business creation requires business details and mandatory owner details.
2. During business creation in the Platform Admin portal, the authorized platform administrator sets the initial password for a new business owner. Initial passwords are never logged, never written to audit metadata, and never exposed in error messages.
3. First-login behavior is documented from verified implementation evidence. No forced password-change-on-first-login requirement is introduced. Email-based password-change, password-reset, invitation, or credential-delivery flows are future scope and must not be designed or implemented in this phase.
4. This owner-password decision is not expanded to manager provisioning unless separately supported by confirmed requirements and existing implementation evidence.
5. A business may be created without an outlet and without a subscription.
6. Each business has exactly one owner at a time. Multiple managers are permitted. Managers may be assigned to one or multiple outlets of the same business; outlet-manager assignment is optional. Add Outlet may support selecting the owner, an existing manager, or provisioning a new manager where safely supported.
7. Existing users are reused where appropriate; duplicate accounts must not be created.
8. The owner has access to every outlet of the business, regardless of which person is the outlet's responsible manager. Managers can access only outlets explicitly assigned to them.
9. When the owner is selected as an outlet's responsible person, full owner access is preserved; a manager-role assignment that narrows owner access must not be created.
10. Ownership transfer is explicit, atomic, and auditable. The previous owner is demoted to manager. The audit action is `platform.business_owner.transfer`, distinct from `platform.owner.transfer` (platform-plane owner transfer).
11. A user may own multiple businesses. No global one-business-per-user restriction exists or is introduced.
12. Suspended or otherwise inactive users are rejected as owner/manager assignment targets until their accounts are reactivated.
13. Existing businesses with zero owners are report-only. Automatic repair is not authorized; any repair requires a separately approved task.
14. Reconciliation requirements for duplicate owners, missing outlet subscriptions, legacy subscriptions, and denormalized data drift are documented in the Stage 3 architecture document.

### Related Policy

- Authoritative target architecture: `docs/architecture/stage_3_ownership_subscriptions_architecture.md` §2-§4, §9.
- Resolves DECISION-OP-01 (Operator/owner onboarding credential flow) for business owners: administrator-set initial password via the Platform Admin portal; no email invitation in this phase.

### Approval Record

- Approved by: ROMS Owner  
- Approval date: 2026-10-17  
- Notes: The initial-owner-password wording reflects the owner's latest clarification and supersedes conflicting earlier draft language about temporary credentials and mandatory first-login password change. Does not authorize implementation.

---

## Decision 004: Strict Read-Only Platform Operators

**Status:** Approved  
**Area:** Platform Access Control  
**Date:** 2026-10-17  

### Context

The shipped three-tier model grants Operators access to several mutating platform routes (outlet profile PATCH via the profile router; platform menu write endpoints) and blocks Operators from read endpoints needed for approved read-only pages (businesses list, plans, audit logs). Frontend navigation filtering alone is not an enforcement boundary.

### Decision

1. Operators have strict read-only access to the approved Platform Admin pages: Overview, Businesses, business/outlet details, Subscriptions, Plans, and Audit Logs.
2. Operators must not mutate businesses, outlets, subscriptions, plans, ownership, platform team membership, audit records, or platform menu data. The existing platform-menu write exception is removed; menu-related Platform Admin access is read-only.
3. Backend authorization (router dependencies) enforces these restrictions; frontend navigation filtering alone is insufficient.
4. Team administration is unavailable to Operators.
5. Operator audit-log responses expose only the minimum fields necessary for support and redact unnecessary sensitive metadata (notably actor email and free-form metadata payloads).
6. Route or data exposure contradicting this policy must be identified and corrected as part of Stage 3.

### Related Policy

- Authoritative target architecture: `docs/architecture/stage_3_ownership_subscriptions_architecture.md` §7.
- Supersedes the Platform Operator definition and the Operator menu-write design in `docs/architecture/platform-access-control-and-team-management.md` §1/§3/§4, and the Operator write access in `docs/architecture/UI_Platform_Admin_Guidance_Flow.md` §6.4.

### Approval Record

- Approved by: ROMS Owner  
- Approval date: 2026-10-17  
- Notes: Product-policy approval for the Stage 3 documentation set. Enforcement changes (router splits, redacted serializers) require separate implementation authorization.