# ROMS — Phase 1D Closure & Next-Phase Architectural Plan

## Executive Summary

Phase 1D (**Platform Admin Control Plane**) has completed all five sub-phases (1D.1 through 1D.5). The internal SaaS control plane (`/platform`) is operational, isolated from tenant operations, protected by super-admin authorization, fully audited, and verified by 47 frontend unit tests (100% pass) and 8 backend unit tests (100% pass).

This document provides a closure audit of Phase 1D, analyzes cross-phase integration and operational gaps, and defines the recommended architecture plan for the next phase.

---

## 1. Feature-by-Feature Status Matrix

| Sub-Phase | Component / Capability | Implementation Status | Backend Endpoint(s) | Key Files | Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1D.1** | **Platform Overview Dashboard** | **Fully Implemented** | `GET /api/v1/platform/businesses` | [`DashboardOverview.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/DashboardOverview.tsx) | Total businesses, registered outlets, trial counts, upcoming expirations (<7d), past-due, and suspended metrics verified. |
| **Phase 1D.2** | **Business Directory & Outlet Drawer** | **Fully Implemented** | `GET /api/v1/platform/businesses`<br>`POST /api/v1/platform/businesses`<br>`POST /api/v1/platform/businesses/{id}/outlets`<br>`POST /api/v1/platform/businesses/{id}/assign-owner` | [`BusinessDirectory.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/BusinessDirectory.tsx)<br>[`OutletDetailDrawer.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/OutletDetailDrawer.tsx) | Search, dual status filters (subscription vs operational), outlet drawer, public slug menu preview links (`/m/:slug`), outlet creation & owner provisioning verified. |
| **Phase 1D.3** | **Subscription Management UI** | **Fully Implemented** | `PATCH /api/v1/platform/businesses/{id}/subscription` | [`SubscriptionsOverview.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/SubscriptionsOverview.tsx)<br>[`SubscriptionEditModal.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/SubscriptionEditModal.tsx) | Editing `subscription_status`, operational `status`, `plan_name`, `max_outlets` with validation, confirmation step, and audit logging verified. |
| **Phase 1D.4** | **Platform Admin Management UI** | **Fully Implemented** | `GET /api/v1/platform/admins`<br>`POST /api/v1/platform/admins/{id}/grant`<br>`POST /api/v1/platform/admins/{id}/revoke` | [`PlatformAdminManagement.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/PlatformAdminManagement.tsx) | Super-admin directory, grant & revoke access with target user confirmation step, and last-admin rejection message handling verified. |
| **Phase 1D.5** | **Platform Audit Log Viewer** | **Fully Implemented** | `GET /api/v1/platform/audit-logs` | [`PlatformAuditLogs.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/PlatformAuditLogs.tsx)<br>[`schemas.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/audit/schemas.py) | Action & business filtering, bounded pagination (limit/offset), preformatted JSON metadata drawer, and deterministic ordering (`created_at DESC, id DESC`) verified. |

---

## 2. Integration & Security Analysis

### A. Authentication & Access Control Isolation
- **Verified Fact**: Platform authentication is strictly separated from tenant business authentication.
- **Routes**: Platform admins sign in at `/pf-login` and access `/platform/*` routes protected by [`RequirePlatformAdmin.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/components/auth/RequirePlatformAdmin.tsx). Sign-out returns users to `/pf-login`.
- **Backend Protection**: All `/api/v1/platform/*` endpoints are protected by `dependencies=[Depends(get_current_platform_admin)]` ([`platform.py:L20`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/v1/platform.py#L20)). Non-platform users receive HTTP 403 Forbidden.

### B. Audit Trail Completeness
- **Verified Fact**: All platform mutations (`business.create`, `update_subscription`, `suspend`, `reactivate`, `outlet.create`, `owner.assign`, `admin.grant`, `admin.revoke`) emit audit log entries in the same database transaction. Passwords and credentials are strictly excluded from audit payloads.

---

## 3. Remaining Known Limitations & Operational Gaps

1. **Tenant Owner Password Reset Workflow**:
   - **Current Limitation**: Platform operators can provision initial owner accounts in Phase 1D.2, but cannot reset an existing restaurant owner's password if the owner is locked out or requests a credential reset.
   - **Operational Impact**: High — requires manual database intervention to assist locked-out tenant owners.

2. **Tenant Support Impersonation ("Log in as Business Owner")**:
   - **Current Limitation**: Platform admins currently cannot view a tenant's business portal (`/admin/*`) or troubleshoot menu/table/order issues without obtaining the tenant owner's password.
   - **Operational Impact**: Medium — limits customer support efficiency.

3. **Unpaginated Business Directory Backend Endpoint**:
   - **Current Limitation**: `GET /api/v1/platform/businesses` returns all businesses in a single list without pagination.
   - **Operational Impact**: Low for current tenant scale (<100 businesses), but should be paginated when tenant scale exceeds 200+ businesses.

4. **Financial Revenue Analytics (MRR/ARR)**:
   - **Current Limitation**: The dashboard features operational metrics (outlets, trial counts, expirations) but no automated revenue calculation.
   - **Reasoning**: Payment gateway integration (Stripe/Razorpay) is not yet attached to subscription flags.

---

## 4. Recommended Next Phase: Phase 1E — Platform Operator Support Tools

### Recommendation & Rationale
Before proceeding to Phase 2 (Tenant Operations & POS/KDS expansion), the SaaS control plane should be finalized by implementing **Phase 1E — Platform Operator Support Tools**.

Phase 1E closes the two remaining operational gaps:
1. **Tenant Owner Password Reset API & Modal**: Platform admins can generate a temporary password or issue a credential reset for an outlet owner.
2. **Support Impersonation ("View Tenant Portal")**: Platform admins can generate a short-lived support token to open and troubleshoot a specific tenant's Business Admin portal (`/admin/*`) with explicit audit logging (`platform.support.impersonate`).

### Key Dependencies
- Depends on completed Phase 1D platform admin authentication and audit logging infrastructure.
- Reuses existing `log_audit()` infrastructure and `RequirePlatformAdmin` frontend route wrappers.

---

## 5. Proposed Incremental Implementation Sequence & Verification Strategy

### Step 1: Backend Support Tools API (Phase 1E.1)
- Add `POST /api/v1/platform/users/{user_id}/reset-password` endpoint.
  - Requires `get_current_platform_admin`.
  - Validates user exists and hashes new password securely.
  - Logs audit event `platform.user.reset_password`.
- Add `POST /api/v1/platform/businesses/{business_id}/impersonate` endpoint.
  - Requires `get_current_platform_admin`.
  - Generates short-lived support access token (15-min expiry) with `is_impersonated: true` claim.
  - Logs audit event `platform.support.impersonate`.
- **Verification Strategy**: Pytest suite in `backend/tests/test_platform_support_tools.py`.

### Step 2: Frontend Owner Password Reset & Support Impersonation UI (Phase 1E.2)
- Integrate "Reset Owner Password" action inside `OutletDetailDrawer.tsx` and `BusinessDirectory.tsx`.
- Add "Log in as Business Owner (Support)" button in `BusinessDirectory.tsx` launching an impersonated tenant session in a support view banner.
- **Verification Strategy**: Frontend RTL test suite in `frontend/src/__tests__/PlatformSupportTools.test.tsx` and `npm run build`.

---

## 6. Deferred Items (Do Not Tackle Yet)

1. **Automatic Subscription Billing Integration (Stripe/Razorpay Webhooks)**: Defer until subscription commercial tier definitions are finalized.
2. **Server-Side Pagination for `GET /platform/businesses`**: Defer until business directory scale exceeds 200+ businesses.
3. **Phase 2 POS/KDS Core Features**: Defer until Phase 1E support tools are completed and approved.
