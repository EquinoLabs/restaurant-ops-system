# ROMS — Phase 2.1: Dedicated Kitchen Display System (KDS) Implementation Plan

## 1. Executive Summary

This document provides a repository-grounded, security-checked implementation plan for **ROMS Phase 2.1 — Dedicated Kitchen Display System (KDS)**.

Based on empirical inspection of the codebase, all backend database models ([`orders/models.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/models.py)), authorization dependencies ([`deps.py:RequireOutletRole`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/deps.py#L50-L77)), and order status transition APIs ([`orders.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/v1/orders.py)) already exist in the repository.

Phase 2.1 implements a dedicated, full-screen, high-contrast Kitchen Display System UI (`/admin/kds`) that connects existing waiter POS order entry directly to kitchen screens with **zero database migrations required**.

---

## 2. Verified Current-State Findings & Code References

### A. Order & OrderItem Models
- **File**: [`backend/app/modules/orders/models.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/models.py)
- **`Order` Model**: Contains `id`, `outlet_id`, `table_id`, `waiter_user_id`, `order_number`, `status`, `order_type`, `total_amount`, `notes`, `created_at`, `updated_at`.
- **`OrderItem` Model**: Contains `id`, `order_id`, `menu_item_id`, `item_name`, `unit_price`, `quantity`, `subtotal`, `special_instructions`.
- **Relationships**: `Order.table` → [`DiningTable`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/tables/models.py) (`table_number`), `Order.waiter` → [`User`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/staff/models.py) (`display_name`), `Order.items` → `List[OrderItem]`.

### B. Timestamps & Elapsed Preparation Timers
- **`Order.created_at`** (TIMESTAMP WITH TIME ZONE) is populated when an order is created ([`service.py:L16-L26`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/service.py#L16-L26)).
- **Elapsed Time Calculation**: Frontend computes `Math.floor((Date.now() - new Date(order.created_at).getTime()) / 60000)` to render dynamic elapsed preparation timers on kitchen tickets (e.g. `5m`, `14m`, `22m`).

### C. Permitted Order Status Transitions
- **File**: [`backend/app/modules/orders/service.py`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/service.py#L157-L186)
- **Valid Statuses**: `pending`, `confirmed`, `in_kitchen`, `served`, `completed`, `cancelled`.
- **KDS Workflow Progression**:
  - `pending` / `confirmed` → New ticket in kitchen queue.
  - Action: **Start Cooking** → calls `PATCH /api/v1/orders/{id}/status` with `status: "in_kitchen"`.
  - Action: **Mark Ready (Bump)** → calls `PATCH /api/v1/orders/{id}/status` with `status: "served"`.

### D. Authorization & Tenant Isolation
- **File**: [`backend/app/api/v1/orders.py:L32-L36`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/api/v1/orders.py#L35)
- **Role Requirement**: `dependencies=[Depends(RequireOutletRole(["owner", "manager", "waiter", "kitchen"]))]`.
- **Tenant & Business Suspension Guard**: `RequireOutletRole` checks user membership and verifies `business.status == "active"`. If suspended, returns HTTP 403 Forbidden.

### E. Explicit Resolution of Item Checkmarks
- **Inspection Result**: `OrderItem` in [`orders/models.py:L54-L77`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/backend/app/modules/orders/models.py#L54-L77) has **no persistent `status` or `is_prepared` column**.
- **Decision**: Per-item checkmarks will **NOT** be included in Phase 2.1 to avoid misleading kitchen staff with ephemeral local UI checkmarks that vanish on page refresh or multi-screen polling. Order-level preparation status (`confirmed` → `in_kitchen` → `served`) will be used. Item-level tracking is deferred to a future sub-phase requiring a database migration.

---

## 3. Proposed KDS UI Architecture & Workflow

### A. Route & Access
- **Route**: `/admin/kds` in [`AppRoutes.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/routes/AppRoutes.tsx).
- **Navigation**: Access link in Business Admin header for staff with `owner`, `manager`, `waiter`, or `kitchen` roles. Includes an "Exit Fullscreen / Admin" button.

### B. Kitchen Layout & Visual Design
- **Dark Theme High-Contrast Grid**: Full-screen layout tailored for kitchen touch monitors and tablets.
- **Header Toolbar**: Outlet selector, active ticket count, live connection indicator, manual refresh button, auto-refresh interval toggle (10s / 30s / Off), and Exit button.
- **Queue Views / Column Filter**:
  1. **Active Kitchen Queue** (`confirmed` + `in_kitchen` tickets).
  2. **Ready for Pickup** (`served` tickets awaiting table delivery).
  3. **All Active Tickets**.

### C. Kitchen Ticket Component Features
Each order card displays:
- **Order Header**: Order number (e.g. `ORD-20261010-004`), order type badge (`Dine-In` vs `Takeaway`), Table number (e.g. `Table T-03`), and Waiter name.
- **Dynamic Elapsed Prep Timer**:
  - `Green` (< 10 minutes elapsed): Normal prep window.
  - `Amber` (10–20 minutes elapsed): Priority warning.
  - `Red Pulsing` (> 20 minutes elapsed): Delayed order alert.
- **Item List**: Quantity badges (e.g. `2x`), Item names, and special instructions highlighted in amber font (`"No onions, extra spicy"`).
- **One-Tap Action Buttons**:
  - For `pending` / `confirmed` tickets: **"Start Cooking"** button (transitions to `in_kitchen`).
  - For `in_kitchen` tickets: **"Mark Ready / Bump Ticket"** button (transitions to `served`).

### D. Auto-Refresh Polling & Concurrency Protection
- **Polling Loop**: Calls `fetchOutletOrders(selectedOutletId, token)` every 10 seconds.
- **Overlapping Request Guard**: Tracks `submittingOrderIds: Set<string>`. While an order status mutation is pending, its bump button shows a spinner and disables duplicate clicks.
- **Network Failure & Expired Auth**: If polling receives HTTP 401/403, redirects to `/login` with clean state notification.

### E. Audio Notification (Web Audio API)
- Triggers a subtle audio chime when new tickets arrive in the queue.
- Includes a UI mute/unmute toggle to respect browser autoplay policies (activates on first user tap).

---

## 4. In-Scope vs. Out-of-Scope Summary

### In-Scope (Phase 2.1)
- `/admin/kds` dedicated view & component suite ([`KDSView.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/kds/KDSView.tsx), [`KDSTicketCard.tsx`](file:///C:/Lakshya/Coding/EquinoLabs/restaurant-ops-system/frontend/src/features/kds/KDSTicketCard.tsx)).
- Live elapsed preparation timer calculation based on `created_at`.
- Status transitions: `confirmed` → `in_kitchen` → `served`.
- Auto-refresh polling (10s), manual refresh, network error handling, and duplicate-click guards.
- Route registration and outlet selection integration.

### Out-of-Scope (Deferred)
- Per-item database preparation tracking (requires Alembic migration).
- Customer mobile QR self-ordering cart (Phase 2.2).
- POS receipt printing & bill settlement (Phase 2.3).
- WebSockets or external real-time message brokers.

---

## 5. Migration Decision

- **Migration Required**: **NO**.
- **Justification**: All required entities (`Order`, `OrderItem`, `DiningTable`, `User`), statuses, and API endpoints already exist in PostgreSQL and SQLAlchemy schemas.

---

## 6. Incremental Implementation Sequence & Verification Strategy

### Step 1: Frontend KDS Component & API Client Integration
- Create `frontend/src/features/kds/KDSTicketCard.tsx`: Order card with timers, items, instructions, and status buttons.
- Create `frontend/src/features/kds/KDSView.tsx`: KDS header, toolbar, ticket grid, auto-refresh polling loop, and audio alert.
- Register route `/admin/kds` in `AppRoutes.tsx`.

### Step 2: Testing & Build Verification
1. **Frontend Unit Tests**: Create `frontend/src/__tests__/KDSView.test.tsx` verifying ticket rendering, timer calculations, status updates, and auto-refresh.
2. **Production Build**: Execute `npm run build` in `frontend/`.
3. **Backend Regression Verification**: Execute `pytest tests/test_orders.py` in `backend/`.

---

## 7. Acceptance Criteria for Phase 2.1

1. Staff can navigate to `/admin/kds` and view active kitchen tickets for their selected outlet.
2. Order cards display order number, table number, waiter name, item quantities, and special instructions.
3. Elapsed preparation timers update dynamically every minute and highlight delayed tickets (>20m).
4. Tapping "Start Cooking" updates order status to `in_kitchen` without page reload.
5. Tapping "Mark Ready" updates order status to `served` and removes ticket from active prep queue.
6. Outlet isolation and business suspension (HTTP 403) are strictly enforced.
