# ROMS — Long-Term Architecture, Product Strategy & Implementation Roadmap

**Document type:** Architecture and product strategy
**Version:** 1.0
**Date:** 10 October 2026
**Status:** Guiding document for future development
**Project:** Restaurant Operations Management System (ROMS)

---

## 1. Purpose of This Document

This document defines the long-term architectural direction of ROMS, how its product experiences should be organized, how the database should evolve, and when future capabilities should be implemented.

ROMS is intended to start as a simple QR-based digital menu and gradually evolve into a restaurant operations platform that can serve multiple businesses, multiple outlets, and different subscription tiers.

The objective is not to implement every planned capability immediately. It is to establish sound architectural boundaries now, implement features incrementally, and avoid major redesigns as the product expands.

This document should be read alongside the existing Technical Specification and Neon PostgreSQL Integration Specification. It supplements those documents rather than replacing their detailed implementation requirements.

### Current implementation status

The application currently has a basic functioning QR scan → digital menu experience. The repository also has an existing FastAPI backend, SQLAlchemy 2.x, Alembic, Neon PostgreSQL integration work, and initial R1 database models and migrations, according to the current development assessment.

Before implementing anything described here, the coding agent must verify the actual repository state. The existence, completeness, and production readiness of each component must not be assumed solely from this document.

The current working functionality is the baseline. Future changes must preserve it.

---

## 2. Product Vision

ROMS should evolve into a modular restaurant software platform rather than a collection of unrelated applications.

The initial product solves a simple problem: customers can scan a QR code and browse a restaurant's menu.

Future versions may support:

* Digital menus and menu management.
* Outlet-specific QR experiences.
* Table-aware ordering.
* Staff-assisted order entry.
* Kitchen order management.
* Payment tracking and online payment integration.
* Billing and sales reports.
* Table and dining-session management.
* Multiple outlets under one business account.
* Subscription plans and feature entitlements.
* Business analytics and operational reporting.

The platform must remain useful at every stage. A restaurant should be able to purchase and use a digital menu without being forced to adopt QR ordering, kitchen management, or a new billing system.

Likewise, a restaurant that wants more functionality should be able to enable additional modules without moving to a different application or duplicating its menu data.

### Core product principles

1. **Incremental delivery:** Implement only the functionality needed for the current release.
2. **Shared platform, distinct experiences:** Different customer and staff workflows can share the same backend and core data.
3. **Optional capabilities:** Restaurants should be able to use the modules appropriate to their operations and subscription.
4. **Business and outlet isolation:** Each business must access only its own authorized data.
5. **Compatibility with existing operations:** ROMS should coexist with traditional billing software and waiter-led ordering when necessary.
6. **Cloud and deployment simplicity:** Prefer a modular monolith over distributed services until measurable requirements justify additional complexity.
7. **Operational reliability:** Order, payment, and billing correctness must take priority over adding features quickly.
8. **No premature infrastructure:** Avoid introducing Redis, Kafka, Kubernetes, microservices, or other operational dependencies without a demonstrated need.

---

## 3. Architecture: One Platform, Multiple Experiences

ROMS should distinguish three concepts: application experiences, functional modules, and subscription entitlements.

These concepts are related, but they are not interchangeable.

### 3.1 Application experiences

An experience is the interface and workflow presented to a particular user.

Examples:

* Public digital menu.
* Customer QR ordering.
* Staff order-entry interface.
* Kitchen display.
* Restaurant administration dashboard.
* Platform administration interface.

Experiences can have different layouts, navigation, permissions, and workflows while communicating with the same backend.

### 3.2 Functional modules

A module represents a business capability implemented in the backend.

Examples:

* Business and outlet management.
* Menu management.
* Table management.
* Orders.
* Kitchen workflows.
* Payments.
* Billing.
* Reporting.
* Subscriptions and entitlements.

Modules should own their business rules and expose clear internal interfaces. Modules may depend on shared functionality, but unrelated modules should not need to know each other's implementation details.

### 3.3 Subscription entitlements

An entitlement determines whether a business is permitted to use a particular capability.

For example, a digital-menu subscription may permit menu publication but not customer order submission.

A higher plan may enable QR ordering, kitchen workflows, and reporting.

The subscription system controls access to capabilities; it should not dictate that every capability requires a separate application or deployment.

---

## 4. Frontend Architecture

### 4.1 Initial direction

Continue with the existing React, Vite, and TypeScript frontend.

Organize the frontend into feature-oriented modules and distinct route groups as functionality grows.

Illustrative route structure:

* `/m/:outletSlug` — public digital menu.
* `/t/:tableToken` — table-specific customer experience.
* `/staff/*` — staff operations.
* `/kitchen/*` — kitchen display.
* `/admin/*` — business and outlet management.
* `/platform/*` — internal platform administration, if required.

These are architectural examples, not mandatory final URLs. Existing routes should not be changed merely to match these examples.

### 4.2 Shared components

The public menu and QR ordering experience should reuse common components, including:

* Menu categories.
* Menu items and descriptions.
* Prices.
* Availability indicators.
* Item images.
* Outlet branding.
* Menu loading and error states.

The QR ordering experience can extend the shared menu with a cart, quantity selection, checkout, order submission, and order tracking.

The digital-menu experience should not require these additional components or backend capabilities to function.

### 4.3 When should frontends become separate applications?

Do not create separate frontend repositories or deployments solely because the product has multiple experiences.

A single frontend application with distinct route groups is the preferred starting point.

Separate frontend applications may be justified later if there are measurable benefits, such as:

* A kitchen display requiring an independent deployment and release cycle.
* A staff application needing a dedicated mobile distribution model.
* Significant differences in performance or offline requirements.
* Independent product ownership or a genuinely separate customer-facing product.

Before splitting an application, evaluate the additional deployment, authentication, shared-component, monitoring, and maintenance costs.

A different URL or visual layout alone is not sufficient justification.

---

## 5. Backend Architecture

### 5.1 Framework decision

Retain FastAPI, SQLAlchemy 2.x, Alembic, and PostgreSQL.

The existing implementation already uses this stack. Replacing it with Django would introduce migration costs without being necessary to support the proposed product architecture.

Django could offer a useful built-in administration interface, but that benefit does not outweigh the cost of a framework migration at this stage. ROMS can implement its administration experience in React and FastAPI.

### 5.2 Modular monolith

The backend should remain a modular monolith: one deployable FastAPI application organized into clearly separated domain modules.

An illustrative structure is:

```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      permissions.py
    db/
      session.py
      base.py
    modules/
      businesses/
      outlets/
      menus/
      tables/
      orders/
      kitchen/
      payments/
      billing/
      reports/
      subscriptions/
    api/
      public/
      staff/
      admin/
```

This is a target organizational pattern, not an instruction to restructure the repository immediately. The coding agent must inspect the current structure and introduce boundaries incrementally.

Each module should own its relevant business rules, schemas, and service logic. Shared infrastructure, database sessions, configuration, and authorization should remain centralized where appropriate.

Avoid a single enormous router or service containing unrelated menu, payment, subscription, and order logic.

### 5.3 Why this scales initially

A modular monolith offers several advantages:

* A single deployment is easier to understand and operate.
* Database transactions can span related business operations.
* Authentication and authorization can be shared.
* Development and testing require fewer infrastructure dependencies.
* Modules can be separated later if a concrete scaling or ownership requirement emerges.

Scaling should initially focus on optimizing database queries, indexing, connection management, and backend deployment rather than distributing the application into multiple services.

---

## 6. Business, Outlet, Menu, and Table Data Model

The data model must represent the real business hierarchy rather than encode relationships as arbitrary fields.

### 6.1 Core hierarchy

The foundational relationship is:

```text
Business
  └── Outlets
       ├── Menu categories
       │    └── Menu items or outlet offerings
       ├── Dining tables
       ├── Orders
       └── Staff memberships
```

A business represents the restaurant company or owner account.

An outlet represents one physical location or operating unit belonging to that business.

A business can have multiple outlets, each with its own settings, operating hours, menu availability, tables, orders, and staff assignments.

### 6.2 Menu ownership and outlet-specific pricing

The initial menu model should be reviewed before expanding it.

If outlets maintain completely independent menus, outlet-scoped categories and menu items are sufficient for the initial implementation.

If outlets share dishes but charge different prices or offer different availability, the platform may eventually benefit from distinguishing:

* A shared business-level menu item.
* An outlet-specific offering with its own price, availability, and operational settings.

Do not introduce a generalized catalog and multiple pricing layers until the actual business requirements justify them. Document the current assumptions and preserve the ability to evolve the model.

Historical order items must snapshot relevant information such as item name, unit price, quantity, and applicable discounts or taxes. Editing a menu item must not silently alter historical orders.

### 6.3 Dining tables

A physical restaurant table must be represented as its own entity. It must not be stored as a field on a menu item or encoded solely as a number in an order.

The eventual `dining_tables` entity may include:

* `id`: internal identifier.
* `outlet_id`: owning outlet.
* `table_number`: staff-facing table identifier.
* `name`: optional descriptive label.
* `qr_token`: unique, unpredictable token for a table-specific QR URL.
* `capacity`: optional seating capacity.
* `is_active`: whether the table can be used.

The database should enforce uniqueness for table numbers within an outlet and uniqueness for QR tokens.

A table number is a human-readable identifier. A QR token is a technical identifier used by the application. Knowing or guessing a table number must not grant access to staff functions or sensitive information.

### 6.4 Orders and tables

An order should reference its outlet and optionally its table.

Conceptually:

```text
orders
  id
  outlet_id
  dining_table_id (nullable)
  order_type
  order_status
  ...
```

The actual schema must follow the existing technical specification and repository conventions.

A takeaway order should not require a table.

A table can receive multiple orders over time. A single table visit may also involve multiple orders.

### 6.5 Dining sessions

A dining session may eventually represent one party's visit to a table.

For example:

```text
Table 12
  └── Dining session
       ├── Order 1
       ├── Order 2
       └── Order 3
```

This can support additional ordering, consolidated billing, split bills, and table turnover.

A session is not the same thing as an order. It should be introduced when the product requires those workflows, not simply because tables exist.

Do not create complex session state machines in the initial digital-menu release.

---

## 7. QR Codes and Customer Entry Flows

QR codes should be treated as entry points into shared application experiences, not as separate applications.

### 7.1 Outlet-level QR code

An outlet-level QR code opens the public menu for an outlet.

It does not automatically assign a table, create an order, establish a dining session, or initiate payment.

This is the simplest customer experience and should remain functional even if all ordering features are disabled.

### 7.2 Table-specific QR code

A table-specific QR code identifies an outlet and a table.

It can open the same public menu while enabling table-aware functionality if the outlet has QR ordering enabled.

The QR code should not directly create an order or authorize a payment. It identifies the intended context; the backend remains responsible for validating the outlet, table, menu, order request, and enabled features.

### 7.3 Shared menu experience

Both entry points should reuse the shared menu implementation.

The experience may adapt based on:

* Which outlet is being visited.
* Whether a table context exists.
* Which customer-facing capabilities are enabled.
* Menu availability and outlet settings.

However, the frontend must not be trusted to enforce subscription entitlements. The backend must validate access to protected operations.

### 7.4 QR security and lifecycle

Table QR tokens should be unpredictable and should not expose internal database identifiers.

The system should support disabling or rotating a token when a QR code is replaced or compromised.

A table QR token is not staff authentication and must not be treated as proof of physical presence at the table. Public QR codes can be photographed or shared.

If stricter controls are required later, the platform can introduce staff confirmation, order acceptance, or other context-specific safeguards.

---

## 8. Subscription and Feature Entitlement Architecture

Subscription capabilities should be represented explicitly rather than scattered across frontend conditionals and backend code.

The eventual model may include:

* `plans`: subscription packages.
* `features`: individual platform capabilities.
* `plan_features`: features included in each plan.
* `subscriptions`: business subscription assignments.
* Subscription status and relevant billing dates.

The exact schema should be finalized when subscriptions become a committed product requirement.

### 8.1 Example product packages

Illustrative packages could be:

**Digital Menu**

* Public QR menu.
* Menu categories and item management.
* Outlet branding and menu publication.

**QR Ordering**

* Digital menu.
* Customer cart and order submission.
* Table-aware ordering where configured.
* Customer order tracking.

**Restaurant Operations**

* QR ordering where enabled.
* Staff order management.
* Kitchen display.
* Operational reports.

**Multi-outlet**

* Additional outlet management.
* Cross-outlet reporting.
* Business-level administration.
* Applicable outlet and staff limits.

These are product hypotheses, not final commercial commitments. Pricing, limits, and entitlements must be validated with actual restaurant customers.

### 8.2 Entitlement enforcement

Entitlements should be checked by the backend before performing protected operations.

For example, a business with menu-only access can publish its menu, but cannot submit customer orders through an endpoint that requires QR ordering.

The frontend may hide or disable unavailable capabilities to provide a better experience. That is not a replacement for server-side enforcement.

### 8.3 Subscription ownership

The default commercial model should allow a subscription to belong to a business, with multiple outlets sharing that subscription when the plan permits it.

If per-outlet billing becomes a business requirement, it can be supported through explicit plan and entitlement rules rather than by treating every outlet as a separate customer account.

Do not build payment collection for ROMS subscriptions until pricing, billing rules, and the intended commercial model are agreed.

---

## 9. Multi-Tenancy, Security, and Data Isolation

ROMS must be designed for multiple businesses from the beginning, even if the initial pilot involves only one business with two outlets.

Every protected resource must be accessed through a verified authorization context.

### 9.1 Ownership rules

The platform must enforce relationships such as:

* An outlet belongs to a business.
* A menu category belongs to the appropriate menu or outlet context.
* A dining table belongs to an outlet.
* An order belongs to an outlet.
* A user may be authorized for one or more businesses or outlets.
* A subscription belongs to the appropriate business account.

A client must not be able to access another business's data by changing an ID in a URL or request body.

### 9.2 Authentication and permissions

Public menu access should not require customer accounts.

Staff and administrative functions must require authentication and authorization. Permissions should distinguish business-level administration, outlet management, staff order handling, and kitchen access where necessary.

Authentication implementation should be driven by the actual release scope. Do not add customer registration simply because staff authentication is required.

### 9.3 Database enforcement

The backend must validate ownership and authorization for every relevant operation.

Database foreign keys, unique constraints, indexes, and transactions should reinforce the application-level rules.

If the product grows to many independent business tenants, evaluate additional isolation measures, including PostgreSQL row-level security, based on the threat model and operational requirements. Do not assume row-level security alone replaces correct application authorization.

---

## 10. Scaling Strategy

Scaling should be driven by actual load, operational problems, and measured bottlenecks rather than anticipated complexity.

### Stage 1: Initial pilot

**Characteristics**

* One business.
* A small number of outlets.
* Public digital menu.
* Limited backend traffic.
* Neon PostgreSQL.
* One FastAPI deployment.

**Approach**

* Keep the existing stack.
* Use Alembic migrations.
* Validate database connectivity and schema correctness.
* Add the indexes needed by actual query patterns.
* Keep frontend and backend deployment simple.
* Monitor database storage, compute, errors, and response times.

No microservices, message brokers, or dedicated caching infrastructure are required.

### Stage 2: Operational workflows

**Characteristics**

* Menu administration.
* Staff order entry.
* Kitchen display.
* Customer ordering where enabled.
* More frequent database writes.

**Approach**

* Keep domain boundaries explicit.
* Use transactions for related order operations.
* Add correct idempotency handling for order submission and payment processing.
* Add request validation, audit records for important administrative actions, and structured error reporting.
* Optimize queries and database connection management.
* Consider Server-Sent Events or another suitable approach for kitchen updates when polling becomes inadequate.

Do not introduce realtime infrastructure before the relevant interface exists.

### Stage 3: Multiple businesses and subscription plans

**Characteristics**

* Multiple restaurant companies.
* Different entitlement configurations.
* More outlets and staff accounts.
* Business-level reporting.
* Higher requirements for data isolation.

**Approach**

* Implement subscription and entitlement enforcement.
* Audit business/outlet scoping throughout the API.
* Add indexes based on real queries.
* Implement pagination for growing lists.
* Review reporting query performance.
* Establish backup, restore, access-control, and operational monitoring procedures.

The modular monolith can continue serving this stage.

### Stage 4: Larger customer base and higher concurrency

**Characteristics**

* More simultaneous customers and staff.
* Larger order history.
* Multiple active kitchen displays.
* More reporting and integration traffic.

**Approach**

* Measure API latency, database utilization, slow queries, connection saturation, and error rates.
* Adjust backend instances and database compute based on observed demand.
* Evaluate caching for genuinely read-heavy workloads, such as public menus, if measurements justify it.
* Introduce background workers for operations that need asynchronous processing.
* Evaluate dedicated reporting strategies if analytical queries interfere with transactional workloads.

Use managed infrastructure where possible and keep the operational burden appropriate for the team.

### Stage 5: Independent services, only if justified

Separate services may become appropriate when a module needs independent scaling, release cycles, fault isolation, or ownership.

Potential candidates could include notification processing, integrations, or heavy reporting.

Before extracting a service, document:

* The bottleneck or operational limitation.
* Why the existing module cannot address it adequately.
* The data ownership boundary.
* Communication and failure-handling requirements.
* Deployment and monitoring costs.

Microservices are a possible future option, not a mandatory destination.

---

## 11. Database and Operational Reliability

The database is central to the correctness of the system.

### 11.1 Database technology

Continue with Neon PostgreSQL and the existing SQLAlchemy/Alembic approach unless an actual requirement demonstrates a need to change.

The free tier is suitable for initial development and experimentation, but production suitability must be evaluated against its storage, compute, connection, backup, and availability characteristics.

### 11.2 Connection management

Use a centralized database configuration.

The backend should read credentials from environment variables, support the intended local development configuration, and handle SSL requirements correctly.

Connection pooling, timeouts, and health checks must be appropriate for the backend deployment environment. Scale-to-zero wake-up delays and transient connectivity failures should be tested before busy restaurant service depends on the system.

### 11.3 Migrations

All schema changes must be represented by reviewed Alembic migrations.

Do not delete or rewrite applied migration history to make a new environment easier to set up.

Do not rely on `Base.metadata.create_all()` as the production schema management mechanism.

Before applying migrations to a real database, verify the target connection and migration status.

### 11.4 Transactional correctness

As order functionality is added:

* Calculate prices on the server.
* Snapshot prices and relevant item details on order creation.
* Validate outlet and menu ownership.
* Use database transactions for logically atomic operations.
* Enforce idempotency where duplicate requests could create duplicate orders or financial effects.
* Keep order, kitchen, and payment states distinct.
* Process verified payment webhooks safely and idempotently.
* Preserve historical financial records according to the agreed retention requirements.

These requirements become increasingly important as the product moves from menu browsing to transactional operations.

---

## 12. Recommended Release Roadmap

The following roadmap defines the intended sequence. It is not permission to implement all releases in one task.

### R1 — Digital Menu Foundation

**Current focus**

* Preserve the functioning QR scan → menu experience.
* Finalize the existing business/outlet/menu schema.
* Complete and verify Neon connectivity.
* Ensure migrations work consistently.
* Establish the public menu API and safe outlet resolution.
* Verify menu rendering, loading states, and unavailable-outlet behavior.
* Document the local development workflow.

**Exit criteria**

* The existing digital menu remains functional.
* Menu data can be retrieved from the intended database.
* Migrations can be applied to a clean database.
* Public access does not expose protected business data.
* Relevant automated tests pass.

Do not implement cart, payments, subscriptions, or kitchen management as part of R1 unless the existing release plan explicitly requires them.

### R2 — Menu Administration

**Capabilities**

* Authorized staff sign-in.
* Menu category and item management.
* Price and availability updates.
* Outlet configuration.
* Validation and auditability for important changes.

**Exit criteria**

* Authorized users can manage only their permitted business and outlet data.
* Changes appear correctly on the public menu.
* Invalid data and unauthorized changes are rejected.

### R3 — Staff Order Management

**Capabilities**

* Staff create and manage orders.
* Support for the relevant order types.
* Clear order lifecycle.
* Historical order-item snapshots.
* Appropriate staff permissions.

**Exit criteria**

* Staff can manage orders without corrupting menu or outlet data.
* Order state changes are validated and persisted correctly.

### R4 — Kitchen Display

**Capabilities**

* Kitchen-facing order queue.
* Preparation status updates.
* Appropriate kitchen permissions.
* Timely propagation of changes.

**Exit criteria**

* Kitchen staff can see and update the relevant orders.
* Repeated updates do not create inconsistent state.
* Realtime or polling behavior is adequate for the actual workflow.

### R5 — Customer QR Ordering and Table Management

**Capabilities**

* Table entities and table-specific QR tokens.
* Customer cart and order submission.
* Outlet and table context validation.
* Table-aware orders.
* Duplicate-submission protection.
* Order tracking.

**Exit criteria**

* Outlet QR menus remain functional.
* Table QR codes resolve to the correct outlet and table.
* The backend calculates prices and validates availability.
* Duplicate requests do not create duplicate orders.
* The system works when a table has multiple orders over time.

Introduce dining sessions only if required for the selected order and billing workflows.

### R6 — Payments and Billing

**Capabilities**

* Payment attempts associated with orders.
* Verified payment webhooks.
* Idempotent payment processing.
* Payment status tracking.
* Bills and order-to-bill relationships as required.
* Reconciliation and failure handling.

**Exit criteria**

* Failed payment attempts do not create duplicate food orders.
* Payment state remains distinct from kitchen and order state.
* Historical financial data is preserved.

This release requires a separate payment and billing design review before implementation.

### R7 — Reporting and Multi-Outlet Management

**Capabilities**

* Outlet-level sales and operational reports.
* Business-level reporting across outlets.
* Staff and outlet management.
* Appropriate data isolation.
* Performance-aware reporting.

**Exit criteria**

* Reports reconcile with underlying orders and payments.
* Cross-outlet data is available only to authorized users.
* Larger datasets do not cause unacceptable degradation of transactional operations.

### R8 — Subscriptions and Product Entitlements

**Capabilities**

* Subscription plans and feature definitions.
* Business subscription assignments.
* Server-side entitlement enforcement.
* Plan limits where justified.
* Upgrade and downgrade behavior.
* Billing integration if commercially required.

**Exit criteria**

* Businesses can use only the capabilities permitted by their entitlements.
* Existing data remains intact when plans change.
* Subscription failures and expirations have explicit behavior.
* Plan enforcement is tested at the API level, not just in the frontend.

Subscription billing, trial periods, refunds, tax treatment, and plan limits must be specified separately before implementation.

### R9 — Growth and Optimization

**Capabilities, as justified**

* Notifications and integrations.
* Additional customer experiences.
* More advanced reporting.
* Performance improvements.
* Selective caching and background processing.
* Independent services if supported by evidence.

This release has no fixed feature list. It should be driven by actual customer needs and measured limitations.

---

## 13. Rules for the AI Coding Agent

This document is a long-term architecture guide, not a request to implement the complete platform immediately.

The coding agent must follow these rules.

### 13.1 Inspect before changing

Before every substantial feature:

1. Inspect the existing implementation.
2. Read the relevant technical specifications and current release plan.
3. Identify the existing models, migrations, API routes, and tests affected.
4. Determine the smallest correct implementation.
5. Report important assumptions and risks before making structural changes.

Do not invent repository state or duplicate existing functionality.

### 13.2 Implement only the current release

The agent must identify the active release and implement only its approved scope.

Future architecture should inform current decisions, but future functionality should not be implemented preemptively.

For example, knowing that table QR ordering is planned should encourage a sound outlet and table relationship. It does not justify implementing the entire ordering, kitchen, payment, and subscription system while finishing the digital menu.

### 13.3 Preserve existing behavior

Every feature must preserve the functioning digital-menu experience unless an approved requirement explicitly changes it.

Use backward-compatible changes where practical. When a breaking change is unavoidable, explain the impact and migration plan.

### 13.4 Avoid speculative abstractions

Do not create generic plugin frameworks, a universal workflow engine, complex feature registries, multiple deployments, or generalized pricing systems without an immediate requirement.

Prefer explicit domain models and simple interfaces that can evolve as requirements become clearer.

### 13.5 Database changes

Before modifying the schema:

* Check existing models and migrations.
* Define constraints and relationships deliberately.
* Consider how existing data will migrate.
* Generate and review Alembic migrations.
* Do not apply changes to production without approval.
* Add relevant tests for ownership, integrity, and failure conditions.

### 13.6 Testing

During implementation, run the smallest relevant test suite.

After completing the task, run the appropriate full suite. Run broader tests earlier if shared or global functionality changes.

Report exactly which tests ran, which passed, which failed, and which manual checks remain.

Do not claim a database, payment provider, or deployment has been verified unless an actual verification succeeded.

### 13.7 Deployment and infrastructure

Do not change Neon project settings, deploy infrastructure, add external services, or introduce additional recurring costs without approval.

Keep secrets out of source control and frontend bundles.

Document operational assumptions and any decisions that require the owner's approval.

### 13.8 When to propose an architectural change

The agent should raise a design review when a feature introduces a significant new concern, such as:

* Cross-business data access.
* Complex financial transactions.
* A new authentication or authorization model.
* Breaking schema changes.
* Independent deployments.
* A new infrastructure dependency.
* Significant additional hosting cost.
* A need to split the monolith into services.

The agent should explain the trade-offs and recommend a path before proceeding.

---

## 14. Architecture Decision Log

The following decisions are the current defaults.

| Decision                              | Current direction            | Revisit when                                               |
| ------------------------------------- | ---------------------------- | ---------------------------------------------------------- |
| Backend framework                     | FastAPI                      | A concrete limitation outweighs migration cost             |
| Backend structure                     | Modular monolith             | Independent scaling or ownership justifies extraction      |
| Database                              | Neon PostgreSQL              | Reliability, capacity, or cost requirements change         |
| ORM and migrations                    | SQLAlchemy 2.x and Alembic   | A specific technical requirement demands otherwise         |
| Frontend                              | React, Vite, TypeScript      | Separate distribution or release needs become concrete     |
| Customer experiences                  | Shared frontend initially    | A separate app offers measurable benefits                  |
| Table representation                  | Separate outlet-owned entity | Detailed operational requirements refine the model         |
| Table QR identification               | Unique, unpredictable token  | Additional security requirements justify stronger controls |
| Subscription ownership                | Business-level by default    | Commercial requirements justify outlet-level billing       |
| Realtime kitchen updates              | Deferred until needed        | Polling is insufficient for the actual workflow            |
| Caching and background infrastructure | Deferred                     | Measured load or operational requirements justify it       |
| Microservices                         | Not initially                | Clear scaling, isolation, or ownership benefits emerge     |

These decisions are intended to prevent unnecessary redesign, not to make future changes impossible.

---

## 15. Immediate Priorities

The current priority is not to implement the entire roadmap.

The next steps are:

1. Complete the Neon database foundation and verify the existing R1 migrations.
2. Confirm that the functioning QR menu reads and displays the correct outlet-specific data.
3. Review the existing menu model against the two-outlet business requirements, particularly menu sharing and outlet-specific pricing.
4. Document the current public QR flow and the distinction between outlet-level and table-level QR codes.
5. Finalize the next release's scope before adding menu administration, staff workflows, or ordering.
6. Maintain a clear release checklist and update the architecture documents when an approved decision changes.

Before committing to table-aware ordering, validate the physical table and order workflows with the restaurant owner. Before implementing subscriptions, validate which modules customers actually want to purchase independently.

The product roadmap should evolve with those findings.

---

## 16. Final Architectural Direction

ROMS should be developed as one coherent platform with multiple user experiences and optional capabilities.

The public digital menu, table QR ordering, staff dashboard, kitchen display, and administrative interface do not need to be separate backend applications. They can share a modular FastAPI backend, PostgreSQL data model, authentication system, and entitlement rules.

Business and outlet relationships form the foundation of the data model. Tables, orders, sessions, payments, and subscriptions should be introduced as distinct domain entities when their respective releases require them.

The platform should scale by improving its existing architecture first and introducing more infrastructure only when real requirements justify the additional complexity.

**The immediate objective is to make the existing digital menu reliable, not to build the entire ecosystem in advance.** Each release should add a coherent capability, preserve existing behavior, pass its acceptance criteria, and leave the next release easier to implement.
