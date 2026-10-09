# ROMS Release 3 (R3) Implementation Plan: Staff Order Management & Table Operations

## Goal Description
Implement **Release 3 (R3 - Staff Order Management & Table Operations)** as specified in the PRD and Technical Specification.

R3 empowers restaurant staff (waiters and managers) to manage dining tables, create table orders with server-calculated price snapshots, track order lifecycle state transitions, and free up tables upon order completion.

---

## Technical Scope for R3

### 1. Database Schema Additions (`Alembic Migration 0003_r3_tables_and_orders`)
- **`tables` Table**:
  - `id` (UUID PK)
  - `outlet_id` (FK $\rightarrow$ `outlets.id`, CASCADE)
  - `table_number` (VARCHAR(30), Unique per outlet)
  - `capacity` (Integer, default 4)
  - `status` (VARCHAR(20), default "available": `available`, `occupied`, `reserved`)
  - Timestamps (`created_at`, `updated_at`)
- **`orders` Table**:
  - `id` (UUID PK)
  - `outlet_id` (FK $\rightarrow$ `outlets.id`, CASCADE)
  - `table_id` (Nullable FK $\rightarrow$ `tables.id`, SET NULL)
  - `waiter_user_id` (Nullable FK $\rightarrow$ `users.id`, SET NULL)
  - `order_number` (VARCHAR(50), Unique per outlet)
  - `status` (VARCHAR(30), default "pending": `pending`, `confirmed`, `in_kitchen`, `served`, `completed`, `cancelled`)
  - `order_type` (VARCHAR(30), default "dine_in": `dine_in`, `takeaway`, `delivery`)
  - `total_amount` (Numeric(12,2), default 0.00)
  - `notes` (TEXT)
  - Timestamps (`created_at`, `updated_at`)
- **`order_items` Table**:
  - `id` (UUID PK)
  - `order_id` (FK $\rightarrow$ `orders.id`, CASCADE)
  - `menu_item_id` (Nullable FK $\rightarrow$ `menu_items.id`, SET NULL)
  - `item_name` (VARCHAR(200)) — snapshot at order creation
  - `unit_price` (Numeric(12,2)) — snapshot at order creation
  - `quantity` (Integer, default 1)
  - `subtotal` (Numeric(12,2))
  - `special_instructions` (TEXT)
  - Timestamps (`created_at`, `updated_at`)

---

### 2. Backend APIs (`/backend/app/api/v1/`)

#### Table Endpoints (`/backend/app/api/v1/tables.py`):
- `GET /api/v1/outlets/{outlet_id}/tables`: List tables for an outlet.
- `POST /api/v1/outlets/{outlet_id}/tables`: Create new table.
- `PATCH /api/v1/tables/{table_id}`: Edit table details/status.

#### Order Endpoints (`/backend/app/api/v1/orders.py`):
- `GET /api/v1/outlets/{outlet_id}/orders`: List active and historical orders with status filtering.
- `POST /api/v1/outlets/{outlet_id}/orders`: Create new order (validates availability, snapshots item prices, calculates subtotal/total, sets table status to `occupied`).
- `GET /api/v1/orders/{order_id}`: Get detailed order record.
- `PATCH /api/v1/orders/{order_id}/status`: Advance order lifecycle status (`pending` $\rightarrow$ `confirmed` $\rightarrow$ `in_kitchen` $\rightarrow$ `served` $\rightarrow$ `completed` $\rightarrow$ `cancelled`). Frees up table status to `available` on completion/cancellation.

---

### 3. Frontend Staff POS & Order UI (`/frontend`)

- **`/staff/orders` Route**:
  - Protected route for staff roles (`owner`, `manager`, `waiter`, `kitchen`).
  - **Live Table Selector Grid**: Visual map of tables with occupancy status.
  - **POS Order Entry Panel**: Tap menu items to add to order ticket, adjust quantities, add special instructions, and submit.
  - **Active Orders Queue**: Cards showing order number, table, elapsed time, status badge, and quick status action buttons.

---

## Verification Plan

1. **Automated Backend Tests (`backend/tests/test_orders_and_tables.py`)**:
   - Test table creation and status updates.
   - Test order creation with price snapshotting and total calculation.
   - Test server validation of item availability.
   - Test order status state transitions and automatic table release.

2. **Automated Frontend Tests (`frontend/src/__tests__/StaffOrders.test.tsx`)**:
   - Test table selection UI.
   - Test order ticket creation and status update buttons.
