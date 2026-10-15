# ROMS Platform Admin Portal — Authoritative Functional Blueprint & UI Flow Specification

**Document Version:** 2.0.0 (Corrected Product Flow)  
**Status:** Authoritative Functional Blueprint  
**Target Path:** `docs/architecture/UI_Platform_Admin_Guidance_Flow.md`  
**Governing Standard:** Restores the agreed ROMS product flow for business-to-outlet hierarchy and independent outlet-specific subscriptions. Replaces previous drawer-based and business-level subscription designs.

---

## 1. Executive Summary & Core Mission

The ROMS Platform Admin Portal is the internal control room for the entire ROMS multi-tenant SaaS platform. It is strictly separated from the tenant-facing Business Manager and restaurant operational apps (POS, KDS, Waiter Ordering, Customer Menu). 

Platform administrators use this portal to:
1. Oversee the platform's commercial and operational health.
2. Onboard and manage restaurant businesses (`Business` entities).
3. Onboard, configure, and inspect individual restaurant locations (`Outlet` entities).
4. Manage independent **outlet-specific subscriptions, 30-day trials, plans, and runtime entitlements**.
5. Inspect and govern platform team access (Owner, Admin, Operator).
6. Maintain complete auditability across all sensitive SaaS actions.

Every administrative action follows a deterministic, safe lifecycle:
**Navigate to dedicated page → Inspect authoritative data → Choose action → Validate input → Confirm privileged action → Commit atomically & audit → Observe immediate feedback.**

---

## 2. Global Information Architecture & Route Hierarchy

The Platform Admin Portal is built on deep-linkable, navigable pages with deterministic URL paths. **Slide-over drawers and lightweight modals must never replace dedicated entity detail pages.**

```
/login                                       -> Platform Admin Sign-in
/platform/dashboard                          -> Platform Overview / KPI Control Room
/platform/businesses                         -> Businesses Directory (1 row per business)
/platform/businesses/:businessId             -> Dedicated Business Detail Page
  ├── Overview & Profile Card
  ├── Outlets Table (All outlets under this business)
  ├── Add Outlet Action
  └── Business Memberships / Owners Table
/platform/outlets/:outletId                  -> Dedicated Outlet Detail Page (also accessible via
                                                /platform/businesses/:businessId/outlets/:outletId)
  ├── Tab 1: Profile & Configuration (Address, Timezone, Currency, Branding)
  ├── Tab 2: Menus & Categories (Categories, Items, Pricing, Availability, Images)
  ├── Tab 3: Public Menu & QR (Digital Menu Preview, QR Code Generation)
  ├── Tab 4: Dining Tables & Table QR (Tables, Capacity, Table QR Codes)
  ├── Tab 5: Staff & Permissions (Outlet Staff Memberships, Roles, Assignment)
  └── Tab 6: Subscription & Entitlements (Outlet Plan, 30-day Trial, Overrides)
/platform/plans                              -> Plan Catalog & Feature Limit Mappings
/platform/subscriptions                      -> Platform-wide Subscriptions Overview & Health
/platform/admins                             -> Platform Team & Access Control (Owner, Admin, Operator)
/platform/audit-logs                         -> SaaS Audit Trail & Activity Inspection
```

---

## 3. Core Domain Model & Invariants

### 3.1 Domain Entities & Hierarchy

```
Platform (SaaS Control Plane)
  └── Business (Commercial & Legal Tenant Account)
        ├── Business Owner (User with 'owner' access across all outlets of the business)
        └── Outlet (Physical or Virtual Restaurant Location) [1..N, No Initial Cap]
              ├── Outlet Subscription (Independent Plan, 30-day Trial, Anniversary)
              ├── Menu Categories & Items
              ├── Dining Tables & Table QR Codes
              ├── Outlet Staff Memberships (Managers, Waiters, Kitchen Staff)
              └── Outlet Entitlement Overrides (Grants & Restrictions)
```

### 3.2 Authoritative Subscription Invariants
1. **Subscriptions are Outlet-Scoped:** Subscriptions belong to individual `Outlet` instances, not the `Business`.
2. **Independent Plans:** Different outlets belonging to the same business may be on completely different subscription plans (e.g., Outlet A on `growth_pos`, Outlet B on `free_qr`).
3. **Independent 30-Day Trials:** Every newly created outlet automatically receives its own 30-day trial starting at creation timestamp (`trial_ends_at = now + 30 days`).
4. **Independent Anniversaries & Billing Cycles:** Each outlet has its own subscription lifecycle, start date, and renewal anniversary.
5. **No Initial Outlet Cap:** There is no initial business-level cap on the number of outlets a business may create (`max_outlets` cap is eliminated from business creation and outlet creation).
6. **Entitlement Resolution Context:** Feature access and limits must be evaluated for the target outlet (`check_entitlement(business_id, feature_code, outlet_id)`).

### 3.3 Access Scope Invariants
1. **Business Owners:** A business owner has authoritative operational access across **all** outlets belonging to their business.
2. **Outlet Staff:** Outlet staff (managers, waiters, kitchen) are strictly scoped to their assigned outlet (`OutletMembership`).
3. **Platform Team Isolation:** Platform roles (Platform Owner, Platform Admin, Platform Operator) never receive automatic tenant memberships or bypass tenant route guards. They manage data exclusively through dedicated control-plane routes (`/api/v1/platform/...`).

---

## 4. Businesses Directory & Dedicated Business Detail Page

### 4.1 Business Directory (`/platform/businesses`)

**Purpose:** Manage registered restaurant businesses across the platform.

**Page Structure & Capabilities:**
- **Table View:** Exactly 1 row per business. Embedded outlet cards must NOT be used here.
- **Columns:**
  - Business Name
  - Operational Status (`Active`, `Suspended`)
  - Outlets Count (`Total Outlets`, `Active Outlets`)
  - Primary Contact / Owner Email (if assigned)
  - Created Date
  - Actions: "View Business" button
- **Search & Filters:** Real-time search by business name or ID; filter by operational status (`all`, `active`, `suspended`).
- **Primary Header Action:** `+ Add Business` button opens the Business Onboarding flow.
- **Row Interaction:** Clicking any row or "View Business" navigates directly to `/platform/businesses/:businessId`.

### 4.2 Business Onboarding Flow (`Add Business`)

**Purpose:** Create a new business, provision its initial primary outlet, set up its initial owner, and initialize the primary outlet's 30-day trial.

**Input Fields & Validation Rules:**
| Field Name | Type | Required | Validation / Default |
| :--- | :--- | :--- | :--- |
| `name` | String | Yes | 2 to 200 characters. Trimmed. |
| `primary_outlet_name` | String | Yes | 2 to 200 characters. Default pre-fills with `[Business Name] Main`. |
| `public_slug` | String | Yes | Unique across all outlets. Alphanumeric with hyphens (`[a-z0-9-]+`). Auto-generated from outlet name. |
| `currency` | String | Yes | 3-letter ISO code. Default: `"INR"`. |
| `timezone` | String | Yes | Valid IANA timezone string. Default: `"Asia/Kolkata"`. |
| `address` | Text | No | Optional physical location address. |
| `owner_email` | String | No | Valid email address. If provided, checks if user exists or creates new owner. |
| `owner_name` | String | Conditional | Required if creating a new owner user via email. |
| `owner_password` | String | Conditional | Required if creating a new owner user via email. Minimum 8 characters. |

**Execution & Behavior:**
1. Atomic backend execution: Provisions `Business`, primary `Outlet`, initial 30-day `OutletSubscription` (`status='trial'`, `trial_ends_at = now + 30 days`), and optional `OutletMembership` (`role='owner'`).
2. No business-level outlet cap (`max_outlets`) is required or enforced.
3. Upon success, displays success confirmation and navigates immediately to `/platform/businesses/:businessId`.
4. On failure (e.g. slug collision, validation error), preserves entered values and highlights specific field errors.

### 4.3 Dedicated Business Detail Page (`/platform/businesses/:businessId`)

**Purpose:** Complete administrative view of a specific business entity and its child outlets.

**Layout & Sections:**
1. **Header Breadcrumbs & Title:**
   - Breadcrumbs: `Platform > Businesses > [Business Name]`
   - Business Name, ID, Created Date, Status Badge (`Active` / `Suspended`).
   - Actions: `Edit Business Profile`, `Suspend Business` / `Reactivate Business`.
2. **Business Profile & Contact Card:**
   - Legal / display name, primary contact email, status, total outlets count.
   - Form to edit business name and contact information.
3. **Outlets Section (Primary Operational Area):**
   - Header with title "Outlets ([count])" and primary action button `+ Add Outlet`.
   - **Outlets Table:**
     - Outlet Name & Public Slug
     - Address & Timezone
     - Status (`Active`, `Suspended`)
     - Subscription Plan (e.g., `Growth POS`, `Starter POS`, `Free QR`)
     - Subscription Status (`Trial (28 days left)`, `Active`, `Past Due`, `Cancelled`)
     - Anniversary / Current Period End Date
     - Action: `Manage Outlet →` (Navigates to `/platform/outlets/:outletId` or `/platform/businesses/:businessId/outlets/:outletId`).
   - Empty State: When a business has no outlets, shows a clear notice and a prominent `Add First Outlet` button.
4. **Business Owners & Access Section:**
   - Table of users who have Owner authority over this business.
   - Shows user display name, email, account status, and assignment date.
   - Action to link/assign another Owner.

---

## 5. Dedicated Outlet Detail Page (`/platform/outlets/:outletId`)

**Purpose:** Comprehensive operational and commercial management of a single outlet location. Accessible via `/platform/outlets/:outletId` or `/platform/businesses/:businessId/outlets/:outletId`.

### Header & Context
- Breadcrumbs: `Businesses > [Business Name] > [Outlet Name]`
- Outlet Name, Public Slug (`/menu/:slug`), Status Badge (`Active` / `Suspended`).
- Quick Link: "Open Public Menu ↗" (opens customer digital menu in new tab).
- Outlet Status Toggle: Suspend / Reactivate outlet.

### Tab Navigation (6 Dedicated Functional Areas)

```
[ Tab 1: Profile & Config ] [ Tab 2: Menus & Items ] [ Tab 3: Public Menu & QR ]
[ Tab 4: Dining Tables & QR ] [ Tab 5: Staff & Access ] [ Tab 6: Subscription & Entitlements ]
```

---

### Tab 1: Profile, Address & Configuration
- **Outlet Information:**
  - Name (Editable, 2-200 chars).
  - Public Slug (Editable with conflict check, warns of broken QR codes if changed).
  - Timezone selector (IANA list).
  - Currency selector (ISO 3-letter).
  - Full physical address (Text area).
- **Dynamic Branding:**
  - Logo URL (with image preview).
  - Cover Image URL (with banner preview).
  - Primary Theme Color (color picker + hex input).
  - Accent Theme Color (color picker + hex input).
- **Save Changes Button:** Validates, saves via `PATCH /api/v1/platform/outlets/:outletId`, audits changes, and refreshes state.

---

### Tab 2: Menu Categories and Menu Items
- **Purpose:** Full platform administration of outlet menu offerings via dedicated platform menu endpoints (`/api/v1/platform/outlets/:outletId/menu/...`).
- **Category Management:**
  - List categories with sort order, status (`active`/`hidden`), item count.
  - Create category (`name`, `sort_order`).
  - Edit/reorder category.
- **Menu Item Management:**
  - Table/list of items grouped by category.
  - Columns: Item Name, Price, Category, Dietary/Spicy tags, Availability (`In Stock` / `86'd`), Status.
  - Actions:
    - `+ Add Item`: Name, description, price, category, dietary tags (veg, non-veg, vegan, gluten-free), spice level.
    - `Edit Item`: Update details, pricing, descriptions.
    - `Toggle Availability`: Instantly 86 / un-86 an item.
    - `Image Upload / Manage`: Upload item photo or remove photo.

---

### Tab 3: Public Menu & QR Management
- **Purpose:** Digital menu configuration, live preview, and high-resolution QR code generation for the outlet.
- **Customer Menu Preview:** Live rendering frame or link to public menu URL (`/menu/:slug`).
- **Digital QR Code Generator:**
  - Visual QR preview encoded with the live public menu URL.
  - Download options: PNG (high resolution for print) and SVG (vector).
  - Instructions for display: Table tent cards, standees, entrance posters.

---

### Tab 4: Dining Tables & Table QR Codes
- **Purpose:** Manage physical dine-in tables and table-specific ordering QR codes.
- **Table Directory:**
  - Table number/identifier (e.g., "T-01", "Patio-4").
  - Seating capacity (e.g., 2, 4, 6, 8).
  - Section / Area name (e.g., "Main Dining", "Terrace", "Bar").
  - Table Status (`Active`, `Inactive`).
- **Actions:**
  - `+ Add Table`: Number, capacity, section.
  - `Edit Table`: Modify number, capacity, section.
  - `Download Table QR`: Generates table-specific QR encoding `/menu/:slug?table=:tableId` for dine-in ordering.
  - `Bulk Print Table QRs`: Generates a printable multi-page sheet of all active table QR codes.

---

### Tab 5: Outlet Staff & Access Permissions
- **Purpose:** Inspect and manage restaurant personnel assigned to this specific outlet.
- **Staff Table:**
  - Display Name, Email, Account Status.
  - Outlet Role: `manager`, `waiter`, `kitchen`, `owner`.
  - Assigned Date.
- **Role Scoping Rules:**
  - Outlet staff roles are strictly scoped to this outlet.
  - Assigning a user as `waiter` on Outlet A does NOT grant them access to Outlet B.
  - Business Owners appear with an indicator "Business Owner (All Outlets)".
- **Actions:**
  - `Assign Staff Member`: Select existing user or enter email, select role (`manager`, `waiter`, `kitchen`), submit.
  - `Change Role`: Update staff member role.
  - `Remove Staff`: Revoke outlet membership.

---

### Tab 6: Subscription, Plan, Trial & Effective Entitlements
- **Purpose:** Independent commercial subscription management and runtime entitlement inspection for this specific outlet.
- **Current Subscription Summary Card:**
  - Current Plan: Plan Code & Display Name (e.g., `Growth POS`).
  - Subscription Lifecycle Status: `Trial`, `Active`, `Past Due`, `Cancelled`.
  - Trial Information: `30-day Trial` with exact countdown (`X days remaining`) and `Trial Ends At` timestamp.
  - Billing Cycle: Start Date, Current Period End (Anniversary), Renewal behavior (`auto-renew` vs `cancel at period end`).
- **Subscription Actions (Platform Admins & Owners only):**
  - `Change Plan`: Dropdown of active plans from Plan Catalog (`Starter POS`, `Growth POS`, `Pro KDS`, `Enterprise`, `Free QR`). Applying changes updates this outlet's subscription only.
  - `Extend Trial`: Add 7, 14, or 30 days to the outlet's trial period.
  - `Update Lifecycle Status`: Mark Active, Suspend, or Cancel with required administrative reason.
- **Effective Entitlements Matrix:**
  - Live table evaluating all features for this outlet:
    - Feature Code (e.g. `pos.orders`, `kds.display`, `menu.digital`, `tables.dine_in`)
    - Authorized Status (`Granted` [green check] / `Denied` [red X])
    - Numeric Limit (`Unlimited`, numeric limit, or `N/A`)
    - Source (`Plan: Growth POS`, `Outlet Grant Override`, `Business Grant Override`, `Restriction Override`)
    - Scope (`outlet`, `business`, `system`)
- **Administrative Overrides Section:**
  - Table of active grants and restrictions applied to this outlet.
  - Action: `+ Create Override` (Grant or Restrict a specific feature, set limit, reason, and expiration).
  - Action: `Revoke Override` (Remove an active override).

---

## 6. Authoritative Lifecycle Workflows

### 6.1 Business Onboarding Workflow
```
Platform Admin
  → Opens /platform/businesses
  → Clicks "+ Add Business"
  → Enters:
      - Business Name (e.g. "Taj Dining Hospitality")
      - Primary Outlet Name (e.g. "Taj Palace Colaba")
      - Public Slug (e.g. "taj-colaba")
      - Currency ("INR") & Timezone ("Asia/Kolkata")
      - Primary Owner Email (e.g. "owner@tajdining.com")
  → Clicks "Create Business"
  → Backend executes atomic provisioning:
      1. Creates Business record (status="active")
      2. Creates primary Outlet record
      3. Provisions independent 30-day trial OutletSubscription for primary Outlet
      4. Links/creates Owner user with OutletMembership(role="owner")
      5. Commits and records platform audit event
  → Portal displays success notification
  → Redirects administrator directly to /platform/businesses/:businessId
```

### 6.2 Outlet Onboarding Workflow
```
Platform Admin
  → Opens /platform/businesses/:businessId
  → Clicks "+ Add Outlet"
  → Enters:
      - Outlet Name (e.g. "Taj Express Bandra")
      - Public Slug (e.g. "taj-bandra")
      - Address, Currency ("INR"), Timezone ("Asia/Kolkata")
  → Submits form
  → Backend executes atomic outlet provisioning:
      1. Validates slug uniqueness across all outlets
      2. Creates Outlet record associated with business_id
      3. Creates independent 30-day trial OutletSubscription:
           - status = "trial"
           - trial_ends_at = now + 30 days
           - plan_id = default starter/growth plan
      4. No business-level max_outlets limit is checked or enforced
      5. Records audit event "platform.outlet.create"
  → Portal displays success notification
  → Navigates administrator directly to /platform/outlets/:newOutletId
```

### 6.3 Outlet Subscription Management Workflow
```
Platform Admin
  → Navigates to /platform/businesses/:businessId
  → Selects outlet from Outlets list → opens /platform/outlets/:outletId
  → Opens "Subscription & Entitlements" Tab
  → Inspects outlet subscription details (Plan, Status, Days remaining in trial)
  → Clicks "Change Plan"
  → Selects new plan (e.g. upgrades from "starter_pos" to "pro_kds")
  → Reviews impact on features and confirms change
  → Backend updates only this outlet's OutletSubscription record
  → Invariant Guarantee: Changing Outlet A's plan has ZERO impact on Outlet B under the same business
  → Refreshes Effective Entitlements matrix to reflect new plan limits immediately
```

### 6.4 Outlet Operations Workflow
```
Platform Admin or Operator
  → Opens /platform/outlets/:outletId
  → Navigates between operational tabs:
      - Menus & Categories: Updates pricing, adds seasonal items, toggles stock availability
      - Dining Tables: Adds new tables, downloads table QR codes
      - Staff: Assigns new kitchen staff member
  → All writes route through dedicated /api/v1/platform/outlets/... endpoints
  → No tenant route bypass is performed
  → Every write produces an auditable platform event with actor attribution
```

---

## 7. Resolution of Documentation Conflicts & Architectural Decisions

| Document / Area | Previous Documented Interpretation | Agreed Product Requirement (Authoritative) | Resolution & Implementation Action |
| :--- | :--- | :--- | :--- |
| `platform-access-control-and-team-management.md` §1 | "Subscriptions remain authoritative at the Business tenant level. Any transition to outlet-level subscriptions is out of scope." | Subscriptions are **strictly outlet-scoped**. Each outlet has its own plan, 30-day trial, and renewal date. | The temporary scoping disclaimer in the access control doc is superseded by the core commercial model. Subscriptions are migrated to `OutletSubscription`. |
| `roms_platform_admin_subscription_architecture.md` | Schema centered on `BusinessSubscription` (`business_subscriptions` table). | Schema must center on **`OutletSubscription`** (`outlet_subscriptions` table with `outlet_id UUID FK`). | Replace `business_subscriptions` with `outlet_subscriptions`. Relate each subscription directly to an `outlet_id`. |
| `Business.max_outlets` Cap | Creation of outlets was capped by `business.max_outlets` and `outlets.max_count` entitlement. | **No initial business-level cap** on the number of outlets a business can create. | Remove the `max_outlets` limit enforcement in `add_outlet_to_business`. Remove `max_outlets` as a mandatory configuration. |
| Owner Decision 001 | Precedence between outlet-scoped and business-scoped overrides. | Outlet-scoped overrides take precedence over business-scoped overrides. | Fully preserved: Runtime entitlement engine evaluates target outlet's subscription plan + outlet overrides; falls back to business overrides only when no outlet override exists. |
| Navigation Flow | Previous Phase 3 used `OutletDetailDrawer` inside `BusinessDirectory`. | Navigation must use dedicated deep-linkable detail pages: `/platform/businesses/:id` and `/platform/outlets/:id`. | Discard the drawer design. Implement dedicated route-based pages for business detail and outlet detail with tabs. |

---

## 8. State Machine & UI Feedback Standards

Every view and tab must handle the complete state spectrum:
1. **Loading State:** Clean skeleton loader with accessible aria attributes. Never show an empty layout or flash error state while data is in flight.
2. **Success State:** Clear, non-intrusive banner or toast confirmation. Form inputs reset or transition to read-only saved view.
3. **Empty State:** Explains what is missing and provides a primary call-to-action button (e.g., "No outlets created yet. Click 'Add First Outlet' to begin.").
4. **Validation Error State:** Client-side field-level red borders with explanatory message below the input. Server-side validation errors (422) mapped directly back to the offending fields. Form inputs preserved.
5. **Conflict State (409):** Explains the uniqueness collision (e.g., "The public slug 'taj-colaba' is already in use by another outlet") and suggests an alternative.
6. **Permission Denied State (403):** Clear message explaining that the user's platform role (e.g., Operator) does not have authorization for commercial or destructive actions. Disables or hides unauthorized controls.
7. **Not Found State (404):** Helpful message indicating the business or outlet does not exist, with a direct link back to `/platform/businesses`.
8. **Concurrent Modification State:** Detects stale state and prompts the user to refresh rather than silently overwriting newer data.