# Product Requirements Document (PRD)
## QR-Based Restaurant Ordering & Operations Platform
**Document version:** 1.0  
**Date:** 9 October 2026  
**Status:** Business concept — discovery and validation  
**Initial market:** Independent restaurants and small restaurant chains in India  
**Initial pilot:** Family-operated restaurant business in Himachal Pradesh  
**Product category:** Restaurant technology / SaaS  
**Working product name:** TBD  

---

## 1. Executive Summary

### 1.1 Product vision
Build an affordable, reliable and easy-to-use restaurant management platform that connects the customer ordering experience, restaurant administration, kitchen operations, billing and payments in one system.
The product will begin with a simple digital menu accessible through a QR code. Over time, it will evolve into a complete restaurant ordering and operations ecosystem that can support multiple outlets under one business.
The long-term vision is to provide smaller restaurant operators with capabilities similar to established restaurant management platforms without unnecessary complexity or expensive customisation.

### 1.2 The opportunity
The initial opportunity comes from a family-operated restaurant business in Himachal Pradesh with two distinct outlets:
- **Traditional restaurant:** Uses an existing billing process, printed menus and waiters who take orders. Its owner values direct interaction with customers.
- **Riverside camp restaurant:** A high-footfall, tourist-oriented venue with busy ordering periods. It reportedly does not currently have a comparable digital billing and ordering system, and customers sometimes leave without paying.

The two locations are approximately 40–60 minutes apart and offer different menus and experiences. The owner spends much of his time at the camp and currently monitors restaurant activity partly through cameras.

This presents several potential problems worth investigating:
- Orders may be difficult to track consistently during busy periods.
- Unpaid bills may create direct financial losses.
- The owner may lack timely, consolidated information about sales and operations.
- Staff may rely on manual processes that become difficult to manage under pressure.
- Each outlet requires its own menu, configuration and operational workflow.

Each outlet requires its own menu, configuration and operational workflow. These problems are not yet fully quantified. The first pilot will validate which ones are most important and whether the proposed software improves them.

### 1.3 Product strategy
The product will be built incrementally:

| Stage | Product capability | Primary objective |
| --- | --- | --- |
| 0 | Customer discovery and workflow mapping | Confirm real problems and constraints |
| 1 | QR-based digital menu | Launch a usable product with minimal operational disruption |
| 2 | Admin menu management | Let restaurant staff maintain their own menus |
| 3 | Staff order entry and tracking | Digitise order records and payment status |
| 4 | Kitchen Display System (KDS) | Route and track orders digitally |
| 5 | Customer QR ordering and cart | Allow customers to place separate orders |
| 6 | Online payment integration | Support secure payment confirmation and reconciliation |
| 7 | Billing and owner dashboard | Provide financial and operational visibility |
| 8 | Multi-outlet SaaS platform | Support external customers and commercial expansion |

### 1.4 Initial business objective
The first objective is not to compete with every established restaurant POS provider. It is to build and deploy a real product in a known business, learn how restaurants use it, identify a measurable improvement, and determine whether another restaurant would pay for it.

---

## 2. Problem Statement

### 2.1 Customer problems
- **Problem A: Manual ordering and limited order visibility** — In the camp restaurant, busy periods can make it difficult to ensure that each order is recorded, prepared, served and paid for correctly.
- **Problem B: Customers leaving without paying** — The camp restaurant reportedly experiences cases where customers leave without settling their bills.
- **Problem C: Limited remote business visibility** — The owner cannot be physically present at both locations simultaneously.
- **Problem D: Fragmented operations** — The two outlets have different menus and workflows.

### 2.2 Why existing solutions may not be sufficient
Petpooja and established restaurant POS products exist. The platform must differentiate through:
- Easier setup for smaller operators.
- Straightforward, transparent pricing.
- SIMPLER workflows for staff with limited technical experience.
- Gradual introduction without forcing a complete operational replacement.

---

## 3. Product Vision and Positioning

### 3.1 Vision statement
Help independent restaurants and small restaurant groups run more organised, visible and accountable operations through a simple digital platform.

### 3.2 Product principles
1. **Data correctness before visual complexity**
2. **Preserve the restaurant's hospitality**
3. **Introduce functionality incrementally**
4. **The backend is the source of truth**
5. **Reliability is a product feature**
6. **Support real restaurant workflows**

---

## 4. Target Customers and Users
Personas include: Restaurant Owner, Restaurant Manager/Supervisor, Waiter/Service Staff, Kitchen Staff, and Customer.

---

## 5. Scope and Release Strategy
- **Release 0:** Discovery & workflow mapping
- **Release 1:** QR-based digital menu (Public menu webpage, QR code access, no cart/ordering)
- **Release 2:** Menu administration (Staff login, category & item management)
- **Release 3:** Staff order management and payment tracking
- **Release 4:** Kitchen Display System (KDS)
- **Release 5:** Customer QR ordering
- **Release 6:** Online payments (Razorpay webhook integration & verification)
- **Release 7:** Billing and owner dashboard
- **Release 8:** Multi-outlet commercial platform

---

## 6. Core Business Requirements
- Menu and outlet management
- Order management
- Kitchen workflow
- Payment management
- Owner reporting

---

## 7. User Roles and Permissions
Platform administrator, Restaurant owner, Outlet manager, Cashier, Waiter, Kitchen staff, Customer.

---

## 8. Proposed Business Model
Setup fees, monthly/annual subscriptions, premium services, multi-outlet packages.

---

## 9. Technical and Operational Constraints
- Source of truth: PostgreSQL & FastAPI backend.
- Order & payment lifecycles separated.
- Real-time updates via WebSockets/SSE backed by persistent database storage.

---

## 10. Explicit Non-Goals for Release 1
Release 1 will not include POS replacement, online payments, customer ordering, kitchen routing, inventory, employee payroll, delivery fleet, or CRM.
