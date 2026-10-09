# Restaurant Operations Management System (ROMS)

A modular, web-based platform for digitizing restaurant operations, from QR-based digital menus to order processing, kitchen coordination, payment tracking, and operational reporting.

The system is designed for independent restaurants and multi-outlet businesses, with a phased implementation strategy that allows restaurants to adopt features incrementally without replacing their entire existing workflow.

> **Project status:** Early development / planning
> **Current focus:** Architecture, workflow validation, and the initial digital menu release.

## Overview

Restaurant Operations Management System (ROMS) aims to provide a unified platform for managing restaurant workflows through a responsive web interface and a centralized backend.

The platform is designed to support:

* QR-based digital menus.
* Menu and item management.
* Staff-managed orders.
* Kitchen Display System (KDS).
* Customer-facing QR ordering and checkout.
* Payment tracking and payment gateway integration.
* Billing, reconciliation, and sales reporting.
* Multi-outlet restaurant management.

The system will be developed incrementally, starting with a digital menu and expanding into operational workflows as requirements are validated in real restaurant environments.

## Architecture

ROMS follows a **modular monolithic architecture** with a centralized API and relational database.

```text
Customer / Staff Browser
          |
          v
 React + TypeScript
          |
        REST API
          |
          v
     FastAPI Backend
          |
    Business Modules
          |
          v
      PostgreSQL
```

The backend separates business logic into domain modules while maintaining a single deployable application. This approach keeps initial development and deployment manageable without preventing future expansion.

## Technology Stack

| Component           | Technology                 |
| ------------------- | -------------------------- |
| Frontend            | React                      |
| Language            | TypeScript                 |
| Build tooling       | Vite                       |
| Backend             | Python, FastAPI            |
| API validation      | Pydantic                   |
| ORM                 | SQLAlchemy                 |
| Database migrations | Alembic                    |
| Database            | PostgreSQL                 |
| API documentation   | OpenAPI / Swagger UI       |
| Testing             | pytest, Vitest, Playwright |
| Local development   | Docker, Docker Compose     |
| Version control     | Git, GitHub                |

Technology versions and deployment providers will be finalized during implementation.

## Planned Modules

### 1. Digital Menu

* Public, mobile-friendly restaurant menu.
* Outlet-specific QR codes.
* Menu categories, item descriptions, prices, and availability.
* No customer account required for menu browsing.

### 2. Menu Administration

* Staff authentication and role-based access.
* Create and update categories and menu items.
* Manage prices, availability, and display order.
* Outlet-scoped permissions.

### 3. Order Management

* Staff-created and customer-submitted orders.
* Unique order identifiers.
* Order-item price snapshots.
* Order lifecycle and cancellation handling.
* Duplicate-submission prevention through idempotency.

### 4. Kitchen Display System

* Kitchen ticket generation.
* Preparation status tracking.
* Live updates and recovery after browser refresh.
* Separation of kitchen status from payment status.

### 5. Payments

* Cash, UPI, and supported online payment methods.
* Payment attempt tracking.
* Server-side payment verification.
* Webhook processing and transaction reconciliation.

### 6. Billing and Reporting

* Bill generation and status management.
* Outstanding-payment tracking.
* Sales summaries and reconciliation reports.
* Auditable financial operations.

### 7. Multi-Outlet Management

* Multiple outlets under one business.
* Outlet-specific menus, tables, and orders.
* Role-based access and consolidated reporting.

*These modules are planned capabilities, not claims that they are already implemented.*

## Development Roadmap

| Release | Focus                                       |
| ------- | ------------------------------------------- |
| R0      | Workflow discovery and technical foundation |
| R1      | Public digital menu and QR access           |
| R2      | Menu administration                         |
| R3      | Staff order management                      |
| R4      | Kitchen Display System                      |
| R5      | Customer QR ordering                        |
| R6      | Online payment integration                  |
| R7      | Billing and operational reporting           |
| R8      | Multi-outlet management                     |

Each release will have defined acceptance criteria, automated tests, and manual verification before subsequent functionality is introduced.

## Design Principles

* **Modular monolith:** Keep deployment simple while separating business domains.
* **Database as source of truth:** Persist operational and financial state in PostgreSQL.
* **Server-side validation:** Calculate prices and totals on the backend.
* **Transactional consistency:** Keep order creation and financial updates atomic where required.
* **Idempotent operations:** Prevent duplicate orders and payment processing.
* **Outlet-level isolation:** Restrict data access according to user permissions and outlet membership.
* **Auditability:** Preserve historical transaction details and record sensitive state changes.
* **Incremental delivery:** Build and validate one release at a time.

## Getting Started

The project is currently in its planning and early development stage. Setup instructions will be added once the initial application scaffold and development environment are finalized.

The intended local environment will use:

* Node.js and npm for the frontend.
* Python and a virtual environment for the backend.
* PostgreSQL for persistent storage.
* Docker Compose for reproducible local development.

## Testing Strategy

Testing will cover:

* Backend business logic and API contracts.
* Database constraints, transactions, and migrations.
* Authentication and outlet-level authorization.
* Order calculation and duplicate prevention.
* Payment verification and webhook idempotency.
* Frontend behavior and error handling.
* End-to-end workflows using Playwright.

Tests will be selected according to the scope of each change, with broader regression testing before release.

## Documentation

Technical specifications, architecture decisions, acceptance criteria, and release plans will be maintained in the project's documentation directory.

Planned documentation includes:

* Technical specification and database relationships.
* API contracts.
* Order and payment state machines.
* Release-specific implementation plans.
* Deployment and operational procedures.

## Project Goals

ROMS is being developed to explore a practical, maintainable approach to restaurant digitization, beginning with a real-world pilot and expanding based on operational feedback.

The long-term objective is to provide a reliable, accessible restaurant operations platform that can be adopted by individual restaurants and scaled to multi-outlet businesses.

## License

License to be determined before public distribution or commercial release.
