# ROMS Release 2 (R2) Implementation Plan: Menu Administration & Staff Authentication

## Goal Description
Implement **Release 2 (R2 - Menu Administration & Staff Authentication)** as specified in the PRD and Technical Specification.

R2 empowers authorized restaurant staff (owners and managers) to manage menu categories, items, prices, and availability directly through an administrative web interface (`/admin/menu`) backed by secure authentication (`/login`).

---

## Technical Scope for R2

### 1. Database Schema Additions (`Alembic Migration 0002`)
- **`users` Table**:
  - `id` (UUID PK)
  - `email` (VARCHAR(254), Unique)
  - `password_hash` (TEXT, hashed with Argon2id/Bcrypt)
  - `display_name` (VARCHAR(150))
  - `status` (VARCHAR(20), default "active")
  - Timestamps (`created_at`, `updated_at`)
- **`outlet_memberships` Table**:
  - `id` (UUID PK)
  - `user_id` (FK $\rightarrow$ `users.id`)
  - `outlet_id` (FK $\rightarrow$ `outlets.id`)
  - `role` (VARCHAR(30): `owner`, `manager`, `waiter`, `kitchen`)
  - Unique constraint: `(user_id, outlet_id)`
- **`audit_logs` Table**:
  - `id` (UUID PK)
  - `business_id` (FK $\rightarrow$ `businesses.id`)
  - `outlet_id` (Nullable FK $\rightarrow$ `outlets.id`)
  - `actor_user_id` (Nullable FK $\rightarrow$ `users.id`)
  - `action` (VARCHAR(100)) — e.g. `PRICE_CHANGE`, `AVAILABILITY_TOGGLE`
  - `entity_type` (VARCHAR(100)), `entity_id` (UUID)
  - `metadata` (JSONB)
  - Timestamps

---

### 2. Backend APIs (`/backend/app/api/v1/`)

#### Authentication & User Endpoints:
- `POST /api/v1/auth/login`: Authenticate staff using email & password, returning JWT bearer token.
- `GET /api/v1/me`: Return current authenticated user info and authorized outlets.

#### Administrative Menu Management Endpoints:
- `GET /api/v1/outlets/{outlet_id}/admin/menu`: Get full admin menu view (includes active, inactive, and out-of-stock items).
- `POST /api/v1/outlets/{outlet_id}/categories`: Create category.
- `PATCH /api/v1/categories/{category_id}`: Edit category (name, description, sort order, active status).
- `POST /api/v1/outlets/{outlet_id}/items`: Create menu item.
- `PATCH /api/v1/items/{item_id}`: Edit menu item (name, description, price, image URL).
- `POST /api/v1/items/{item_id}/availability`: Quick toggle item availability (`is_available: true/false`).

---

### 3. Frontend Web Admin UI (`/frontend`)

- **`/login` Route**: Staff login page with email & password inputs.
- **`/admin/menu` Route**:
  - Protected route (requires valid staff authentication).
  - Outlet selector dropdown (for managers/owners with access to multiple outlets).
  - Category manager: Add/edit categories, drag or change display order.
  - Item manager: Add/edit menu items, update prices, toggle daily availability on/off.
  - Audit history panel: View recent price changes and availability edits.

---

## Verification Plan

1. **Automated Backend Tests (`backend/tests/test_admin_menu.py`)**:
   - Test password hashing and staff authentication.
   - Test RBAC & outlet-scoped authorization (a staff member cannot modify another outlet's menu).
   - Test category and item CRUD operations.
   - Test availability toggle API and audit log entry generation.

2. **Automated Frontend Tests (`frontend/src/__tests__/AdminMenu.test.tsx`)**:
   - Test login form validation and error handling.
   - Test menu item availability toggle UI state.
