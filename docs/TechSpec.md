# Technical Specification (Tech Spec)
## Restaurant Ordering & Operations Platform
**Version:** 1.0  
**Date:** 9 October 2026  
**Status:** Approved for technical planning  
**Document type:** Engineering implementation specification  

---

## 1. Technical Objectives
Build a web-based restaurant platform supporting:
- QR-based digital menus
- Menu & category management
- Staff-managed orders
- Kitchen order processing
- Customer QR ordering & cart checkout
- Payment tracking & online payment integration
- Billing, sales reporting, & outstanding-payment visibility
- Multiple outlets under one restaurant business

---

## 2. Scope and Release Boundaries

| Release | Scope |
| --- | --- |
| R0 — Discovery | Validate workflows, map existing systems, document menu and outlet structure |
| R1 — Digital menu | Public menu accessible through an outlet-specific QR code |
| R2 — Menu administration | Staff login, categories, items, prices, availability |
| R3 — Staff order management | Create and manage orders, record payment status |
| R4 — Kitchen display | Kitchen tickets and preparation states |
| R5 — Customer ordering | QR menu, cart, order submission |
| R6 — Online payments | Payment gateway, verified payment events, refunds where required |
| R7 — Billing and reports | Bills, reconciliation, outstanding amounts, owner dashboard |
| R8 — Multi-outlet SaaS | Business-level administration, outlet management, subscription and onboarding features |

---

## 3. Technology Stack

- **Frontend:** React + Vite + TypeScript
- **Backend API:** Python + FastAPI
- **API Validation:** Pydantic
- **ORM:** SQLAlchemy 2.x
- **Migrations:** Alembic
- **Database:** PostgreSQL
- **Local Dev:** Docker + Docker Compose
- **Testing:** pytest, HTTPX, Vitest, Playwright

---

## 4. Multi-Tenant and Outlet Hierarchy
```text
Business
  ├── Outlet A
  │    ├── Tables, Menu, Orders, Payments, Kitchen tickets
  └── Outlet B
       ├── Tables, Menu, Orders, Payments, Kitchen tickets
```

---

## 5. Core Database Schema Overview
- `businesses`
- `outlets`
- `users`
- `outlet_memberships`
- `dining_tables`
- `menu_categories`
- `menu_items`
- `dining_sessions`
- `orders`
- `order_items`
- `payments`
- `payment_events`
- `kitchen_tickets`
- `bills`
- `bill_orders`
- `audit_logs`

---

## 6. Implementation Rule
Implement one release at a time. R1 is the first production deliverable: an outlet-specific digital menu with QR access backed by FastAPI and PostgreSQL.
