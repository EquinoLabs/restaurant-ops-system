# ROMS — Phase 2: Tenant Operations Readiness & Implementation Plan

## Executive Summary

Following the closure of Phase 1D (Platform Control Plane) and security design of Phase 1E (Support Tools Security), this document outlines the **Phase 2 Tenant Operations Readiness Audit** and defines the recommended **first end-to-end implementation slice**.

Based on empirical inspection of the codebase, the backend database models (`Order`, `OrderItem`, `DiningTable`, `MenuItem`), authorization dependencies (`RequireOutletRole`), and CRUD endpoints (`orders.py`, `tables.py`, `public_menu.py`) are already implemented.

The recommended **Phase 2.1 Implementation Slice** is a **Dedicated Kitchen Display System (KDS) & Real-Time Order Prep Management View**, which connects existing POS waiter order entry directly to kitchen screens with zero database migrations required.

---

## 1. Current-State Capability Matrix

| Operational Capability | Technical Status | Backend API / Models | Frontend Views | Verified Gaps & Findings |
| :--- | :--- | :--- | :--- | :--- |
| **Public QR Menu Browsing** | **Implemented & Verified** | `GET /api/v1/public/outlets/{slug}/menu`<br>`GET /api/v1/public/outlets/{slug}/qr` | [`PublicMenuView.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/public-menu/PublicMenuView.tsx) | Displays active categories, items, prices, descriptions, branding, and PNG QR code generator. Read-only for customers. |
| **Dining Table Management** | **Implemented & Verified** | `GET /api/v1/outlets/{id}/tables`<br>`POST /api/v1/outlets/{id}/tables` | [`TableSelectorGrid.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/staff-orders/TableSelectorGrid.tsx) | Outlets manage table numbers and seating capacities. Tables link to orders via `table_id`. |
| **Waiter POS Order Entry** | **Implemented & Verified** | `POST /api/v1/outlets/{id}/orders`<br>`GET /api/v1/outlets/{id}/orders` | [`OrderEntryPanel.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/staff-orders/OrderEntryPanel.tsx) | Staff select table, pick menu items, specify quantities and special instructions, and create orders. Snapshots `item_name`, `unit_price`, `subtotal`. |
| **Active Order Queue & Status Updates** | **Implemented & Verified** | `PATCH /api/v1/orders/{id}/status` | [`ActiveOrdersQueue.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/staff-orders/ActiveOrdersQueue.tsx) | Supports status flow: `pending` → `confirmed` → `in_kitchen` → `served` → `completed` / `cancelled`. |
| **Dedicated Kitchen Display System (KDS)** | **Partially Implemented (API exists, UI merged into POS)** | `GET /api/v1/outlets/{id}/orders?status=...`<br>`PATCH /api/v1/orders/{id}/status` | Merged inside [`StaffOrdersView.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/staff-orders/StaffOrdersView.tsx) | APIs support `kitchen` role and order status transitions, but lack a dedicated full-screen KDS board optimized for kitchen monitors/tablets. |
| **Customer QR Self-Ordering** | **Missing** | No public `POST /public/outlets/{slug}/orders` endpoint | No customer shopping cart on `/m/:slug` | Customers cannot place orders directly from their mobile phones via QR code scan. |
| **POS Receipt & Payment Settlement** | **Missing** | `Order.total_amount` exists, but no payment model | No bill print / settlement modal | Orders transition to `completed`, but lack tax breakdowns (GST/VAT), payment methods (Cash/UPI/Card), or receipt printing. |

---

## 2. End-to-End Restaurant Operational Workflow

The diagram below illustrates the end-to-end tenant order lifecycle from order capture to fulfillment:

```
┌─────────────────────────┐       ┌─────────────────────────┐       ┌─────────────────────────┐
│   1. ORDER CAPTURE      │       │  2. KITCHEN PREPARATION │       │ 3. SERVICE & COMPLETION │
│  (Waiter POS or QR Scan)│──────>│      (Dedicated KDS)    │──────>│   (Table Service & POS) │
└─────────────────────────┘       └─────────────────────────┘       └─────────────────────────┘
  - Pick Table                    - Live Order Tickets Stream         - Mark Order "Served"
  - Select Menu Items             - Elapsed Preparation Timer         - Settle Bill / Payment
  - Add Special Instructions      - One-Tap "Start Prep"              - Mark Order "Completed"
  - Submit Order ("Confirmed")    - One-Tap "Mark Ready" ("Served")   - Table Freed ("Available")
```

---

## 3. Recommended Implementation Slice: Phase 2.1 — Dedicated KDS & Order Fulfillment Board

### A. Rationale & Value
Optioning a **Dedicated Kitchen Display System (KDS)** as the first Phase 2 slice is the highest-value, lowest-risk operational milestone:
1. **Zero Database Migrations Required**: The `Order` and `OrderItem` models ([`orders/models.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/models.py)), backend service functions, and `PATCH /api/v1/orders/{id}/status` endpoints **already exist and are fully tested**.
2. **Immediate Operational Impact**: Solves the biggest tenant pain point — kitchen staff currently have to use the waiter-focused POS interface (`StaffOrdersView.tsx`) to track food preparation.
3. **Foundation for QR Self-Ordering**: Once the KDS is dedicated and real-time, customer QR orders (Phase 2.2) can immediately feed into a proven kitchen preparation pipeline.

---

### B. In-Scope vs. Out-of-Scope Behaviors

#### In-Scope (Phase 2.1)
- **Dedicated KDS Route & View**: Add `/admin/kds` route in Business Admin navigation.
- **Kitchen-Optimized Card Grid**: High-contrast, large-font order tickets showing order number, table number, order type (`dine_in`, `takeaway`), elapsed preparation timer (color-coded: Green < 10m, Amber 10-20m, Red > 20m), special instructions, and item quantities.
- **One-Tap Kitchen Status Transitions**:
  - `Confirmed` → `In Kitchen` ("Start Cooking").
  - `In Kitchen` → `Served` ("Food Ready / Bump Ticket").
- **Live Auto-Refresh Polling**: Configurable auto-refresh (e.g. every 10 seconds) or refresh button with visual indicator.
- **Audio / Visual New Order Alert**: Play subtle notification chime when a new ticket enters the queue.
- **Filter by Ticket Status**: Tabs for `Active Prep` (`confirmed` + `in_kitchen`), `Ready for Pickup` (`served`), and `All Recent`.

#### Out-of-Scope (Deferred to Sub-Phases 2.2 & 2.3)
- Customer mobile cart and QR order placement (`POST /public/...`).
- Thermal receipt printer hardware integration (POS billing).
- Ingredient inventory stock deduction.
- Integrated credit card payment processing (Stripe/Razorpay).

---

### C. Technical Specifications & File Touch Points

#### Frontend Components
1. Create `frontend/src/features/kds/KDSView.tsx`: Full-screen, high-contrast dark theme kitchen preparation board.
2. Create `frontend/src/features/kds/KDSTicketCard.tsx`: Individual kitchen ticket component with timer, item checkmarks, and bump actions.
3. Update `frontend/src/routes/AppRoutes.tsx`: Add route `/admin/kds` guarded by `ProtectedRoute`.
4. Update Business Admin Navigation: Add "Kitchen Display (KDS)" link in header/sidebar for users with `owner`, `manager`, `waiter`, or `kitchen` roles.

#### Backend & Security Considerations
- **Endpoint Reuse**: Calls existing `GET /api/v1/outlets/{outlet_id}/orders` and `PATCH /api/v1/orders/{order_id}/status`.
- **Authorization Enforcement**: Endpoint dependency `RequireOutletRole(["owner", "manager", "waiter", "kitchen"])` ([`orders.py:L35`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/v1/orders.py#L35)) verifies user membership and enforces active business status.
- **Business Suspension Guard**: Suspended businesses automatically receive HTTP 403 Forbidden when accessing `/outlets/{id}/orders`.

---

## 4. Phase 1E Implications Check

- **Verification**: None of the Phase 1E support tool capabilities (password reset, support impersonation) are technical or operational blockers for Phase 2.1 KDS.
- Kitchen staff and managers authenticate at `/login` using existing user credentials verified by [`deps.py:get_current_user`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/deps.py#L15-L38).

---

## 5. Incremental Sequence & Subsequent Milestones

```
┌─────────────────────────────────────────┐
│ Phase 2.1: Dedicated Kitchen Display    │ ◄── RECOMMENDED NEXT SLICE
│ (KDS View & Ticket Fulfillment Board)   │     (Zero DB Migrations, Uses Existing Order APIs)
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ Phase 2.2: Customer QR Self-Ordering    │
│ (Public Cart, Table QR Order Placement) │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ Phase 2.3: POS Bill Settlement          │
│ (Receipt Print, Taxes, Payment Modes)   │
└─────────────────────────────────────────┘
```

---

## 6. Targeted Verification Strategy & Acceptance Criteria

### Acceptance Criteria for Phase 2.1 (KDS)
1. Kitchen staff can open `/admin/kds` and view active tickets for their selected outlet.
2. Order cards display order number, table number, item names, quantities, and special instructions.
3. Elapsed preparation timers update dynamically and indicate delayed orders.
4. One-tap "Start Cooking" updates order status to `in_kitchen`.
5. One-tap "Mark Ready" updates order status to `served` and removes ticket from active prep view.
6. Outlet boundary and active business operational status are strictly enforced.

### Test Strategy
- **Frontend Unit Tests**: Create `frontend/src/__tests__/KDSView.test.tsx` testing ticket rendering, timer calculations, status updates, and auto-refresh.
- **Production Build Verification**: Run `npm run build` in `frontend/` to ensure zero TypeScript compilation errors.
- **Backend Test Verification**: Run existing `pytest tests/test_orders.py` to confirm zero regression on order status APIs.
