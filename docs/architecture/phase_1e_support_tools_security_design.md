# ROMS — Phase 1E: Support Tools Security & Workflow Design

## 1. Overview & Repository Current State

This document provides a security-focused architecture design for **ROMS Phase 1E (Platform Support Tools & Owner Account Recovery)**, based on empirical inspection of the repository authentication, JWT issuance, authorization dependencies, and frontend context.

---

## 2. Current State Code Inspection & Verified Facts

### A. Authentication & Password Hashing
- **File**: [`backend/app/core/security.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/core/security.py)
- **Functions**: `hash_password()`, `verify_password()`, `create_access_token()`, `decode_access_token()`.
- **Mechanism**: Plaintext passwords hashed with `bcrypt` ([`security.py:L9-L24`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/core/security.py#L9-L24)). JWT tokens signed with `settings.JWT_SECRET_KEY` and algorithm `HS256` ([`security.py:L27-L44`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/core/security.py#L27-L44)). Default token expiry is 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES = 10080`).
- **Limitation**: JWT validation is currently **stateless**. The backend has no token revocation table, session store, or `password_changed_at` invalidation check. Once issued, a JWT remains valid until its `exp` timestamp unless the user account status changes to inactive.

### B. User Authorization & Role Dependencies
- **File**: [`backend/app/api/deps.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/deps.py)
- **Functions**: `get_current_user()`, `get_current_platform_admin()`, `RequireOutletRole`.
- **Mechanism**: `get_current_user()` checks `user.status == "active"`. `get_current_platform_admin()` verifies `user.is_platform_admin == True`. `RequireOutletRole` verifies `OutletMembership` for tenant staff and enforces business operational status (`business.status == "active"`).

### C. Owner Provisioning & Password Management
- **File**: [`backend/app/modules/businesses/platform_service.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/businesses/platform_service.py)
- **Function**: `assign_owner_to_outlet()` ([`platform_service.py:L250-L325`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/businesses/platform_service.py#L250-L325)).
- **Mechanism**: Platform admins provision initial owner accounts with email, display name, and password.
- **Current Gap**: There is **zero password reset, forgot-password, or account recovery code** anywhere in the backend or frontend.

### D. Email Infrastructure Status
- **Verified Code Fact**: ROMS has **no email sending service** (SMTP, SendGrid, Mailgun, AWS SES) or email templates configured in the codebase. `requirements.txt` contains no email libraries (`fastapi-mail`, `boto3`, `sendgrid`).

### E. Frontend Token Storage & Auth State
- **Files**: [`frontend/src/features/authentication/AuthContext.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/authentication/AuthContext.tsx), [`frontend/src/components/auth/RequirePlatformAdmin.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/components/auth/RequirePlatformAdmin.tsx).
- **Mechanism**: Tokens stored in browser `localStorage` (`roms_auth_token`). `AuthContext` validates tokens against `GET /api/v1/auth/me`.

---

## 3. Owner Account Recovery Architecture

### A. Proof of Account Control & Delivery Channels

Because ROMS does not currently have email delivery infrastructure, owner account recovery must support two distinct channels:

```
                  ┌─────────────────────────────────────────┐
                  │          Owner Account Recovery          │
                  └────────────────────┬────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│  Channel A: Platform-Assisted│              │  Channel B: Self-Service     │
│  (No Email Infra Required)   │              │  (Requires Email Provider)   │
├──────────────────────────────┤              ├──────────────────────────────┤
│ 1. Owner contacts support    │              │ 1. Owner enters email on UI  │
│ 2. Admin verifies out-of-band│              │ 2. System dispatches link    │
│ 3. Admin generates single-use│              │ 3. Owner clicks email link   │
│    setup URL / reset token   │              │ 4. System validates & resets │
└──────────────────────────────┘              └──────────────────────────────┘
```

#### Channel A: Platform-Assisted Recovery (Immediate Capability)
1. Restaurant owner submits support ticket or contacts ROMS support out-of-band.
2. Platform admin verifies owner identity via business registration details (GSTIN, legal name, primary outlet slug).
3. Platform admin clicks "Generate Single-Use Password Reset Link" in [`BusinessDirectory.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/platform-admin/BusinessDirectory.tsx).
4. System generates a 30-minute single-use reset URL containing a secure token. Platform admin delivers link to verified owner via support channel.

#### Channel B: Self-Service Email Recovery (Requires Infrastructure Dependency)
1. Owner submits email at `/forgot-password`.
2. System generates single-use token and sends email via SMTP/SendGrid.
3. Owner clicks link and submits new password at `/reset-password?token=...`.
4. Requires configuring `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` in `app/core/config.py`.

---

### B. Reset Token Design & Single-Use Enforcement

1. **Token Format**: 256-bit cryptographically secure random token (`secrets.token_urlsafe(32)`). Never use JWTs for reset links as JWTs cannot be invalidated without storage.
2. **Database Storage**:
   - Create table `password_reset_tokens`:
     - `id` (`UUID`, PK)
     - `user_id` (`UUID`, FK `users.id`, indexed)
     - `token_hash` (`VARCHAR(64)`, SHA-256 digest of plaintext token, indexed)
     - `expires_at` (`TIMESTAMP WITH TIME ZONE`, default `now() + 30 mins`)
     - `used_at` (`TIMESTAMP WITH TIME ZONE`, nullable)
     - `created_by_admin_id` (`UUID`, nullable, FK `users.id` for platform-assisted resets)
3. **Single-Use Verification Logic**:
   - When token is submitted:
     1. Hash incoming plaintext token: `h = sha256(token)`.
     2. Lookup record `WHERE token_hash == h`.
     3. Reject if record not found, `used_at IS NOT NULL`, or `expires_at < now()`.
     4. Set `used_at = now()`, update `user.password_hash = hash_password(new_password)`.

---

### C. Active Session Revocation Strategy

To prevent an attacker who holds a stolen JWT from retaining access after a password reset:
1. Add `password_changed_at` (`TIMESTAMP WITH TIME ZONE`, nullable) column to `users` table.
2. When password is updated, set `user.password_changed_at = now()`.
3. In [`get_current_user`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/deps.py#L15-L38):
   - Compare token `iat` (issued at timestamp) with `user.password_changed_at`.
   - If `token_iat < user.password_changed_at`, raise `AuthenticationError("Session expired due to password change. Please log in again.")`.
4. This provides **instant, stateless revocation of all active JWT sessions** across devices without requiring a Redis session store.

---

### D. Security & Audit Controls

- **Rate Limiting**: Limit `/auth/forgot-password` requests to max 3 per email per hour. Limit `/auth/reset-password` verification attempts to max 5 per IP per hour.
- **Generic Responses**: `/auth/forgot-password` always returns `"If an account matches that email, a password reset link has been dispatched."` (prevents user enumeration).
- **Audit Logging**: Log `platform.owner.reset_password` or `user.password_reset` with `actor_user_id`, `target_user_id`, `channel` (`"platform_assisted"` or `"self_service"`), and outcome. Exclude plain passwords, hashes, and reset tokens.

---

## 4. Support Access & Impersonation Architecture

### A. Evaluation of Support Access Options

| Option | Description | Operational Benefit | Attack Surface & Risk | Auth Requirements | Implementation Cost | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Option A: Improved Tenant Diagnostics** | Add read-only platform-admin diagnostic endpoints (e.g. `GET /platform/businesses/{id}/diagnostics` returning outlet count, category active states, order counts). | Solves 80% of support issues (identifying misconfigured menus or inactive outlets) directly from control plane. | **Minimal**. Reuses `get_current_platform_admin`. Zero identity blending or tenant session tampering. | Requires `get_current_platform_admin`. | **Low** (1-2 days). | **RECOMMENDED FOR PHASE 1E** |
| **Option B: Read-Only Time-Limited Support Token** | Issue a 15-min support token allowing platform admin to open `/admin` portal in read-only mode (`GET` requests only). | Admin can visually inspect menu layout and order screens as owner sees them. | **Moderate**. Short-lived token. Rejects `POST`/`PUT`/`PATCH`/`DELETE` calls on tenant routes. | Token claims: `is_support_session: true`, `permissions: "read_only"`, `target_business_id`. Middleware blocks mutations. | **Medium** (3-4 days). | **RECOMMENDED FOR FUTURE ENHANCEMENT** |
| **Option C: Write-Capable Impersonation** | Issue a full-privilege owner session token for platform admin to make mutations on tenant menu/orders/staff. | Admin can edit tenant menu or table layout on behalf of owner. | **HIGH / SEVERE RISK**. Rogue admin can alter tenant prices, delete data, or exfiltrate customer information. Blurs accountability. | Requires dual-approval, ticket ID parameter, explicit banner UI, and per-mutation audit logging. | **High** (5-7 days). | **DEFERRED / NOT RECOMMENDED** |

---

### B. Required Controls if Support Token (Option B/C) is Implemented

1. **Mandatory Ticket & Reason Capture**: `POST /platform/businesses/{id}/support-session` requires body `{"reason": "Troubleshooting menu visibility", "ticket_id": "TICK-1042"}`.
2. **Short Expiry**: Max 15 minutes (`expires_delta = timedelta(minutes=15)`). Non-renewable.
3. **Explicit JWT Support Claims**:
   ```json
   {
     "sub": "user_id_of_owner",
     "actor_admin_id": "user_id_of_platform_admin",
     "is_support_session": true,
     "support_role": "read_only",
     "target_business_id": "business_uuid",
     "exp": 1791599999
   }
   ```
4. **Visible Support Banner**: Frontend detects `is_support_session` in token and renders an amber top banner: `"SUPPORT SESSION ACTIVE — Viewing as Himalayan Bistro (Read-Only). Session expires in 12m."`
5. **Mutation Guard Middleware**: Backend `RequireOutletRole` dependency checks:
   ```python
   if payload.get("is_support_session") and payload.get("support_role") == "read_only":
       if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
           raise ForbiddenError("Mutations are prohibited during read-only support sessions.")
   ```
6. **Prohibited Support Actions**: Support sessions MUST NOT be allowed to access `/platform/*`, manage platform admins, or perform password resets.

---

## 5. Are Phase 1E Capabilities Blockers for Phase 2?

### Detailed Blockers Analysis

| Phase 1E Capability | Technical Requirement for Phase 2 POS/KDS? | Operational Blocker for Development? | Recommendation & Priority |
| :--- | :--- | :--- | :--- |
| **Owner Password Reset** | **NO**. Phase 2 POS/KDS features run inside the tenant environment (`/admin` and `/m/:slug`). Owners use credentials created during business provisioning. | **NO**. Developers and test tenant owners have established login credentials in `conftest.py` and seed scripts. | Non-blocker. Can be implemented alongside or after Phase 2. |
| **Support Impersonation** | **NO**. Support impersonation is an internal administrative tool, not a core runtime dependency for POS order processing or KDS screens. | **NO**. Tenant portal features can be tested directly using tenant owner credentials. | Non-blocker. Diagnostic tools (Option A) are sufficient. |

### Conclusion
**Phase 1E is NOT a technical or operational blocker for Phase 2.** Phase 2 (POS, KDS, Order Management, QR Menu Ordering) can proceed immediately. Phase 1E features can be scheduled based on operational support needs.

---

## 6. Recommended Implementation Sequence

When Phase 1E is scheduled for execution, implement in this sequence:

1. **Step 1 (Schema & Session Revocation)**:
   - Add `password_changed_at` column to `users` model.
   - Update [`get_current_user`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/deps.py) to check `token_iat < user.password_changed_at`.
2. **Step 2 (Platform-Assisted Password Reset)**:
   - Add `POST /api/v1/platform/users/{user_id}/reset-password` endpoint.
   - Update `OutletDetailDrawer.tsx` to add "Reset Owner Password" button.
3. **Step 3 (Tenant Health Diagnostics)**:
   - Add `GET /api/v1/platform/businesses/{id}/diagnostics` (Option A) providing instant support visibility without impersonation risks.
