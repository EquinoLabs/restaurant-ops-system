# ROMS — Multi-Application Architecture and Product Flow
## Repository Audit and Architecture Proposal for the Local AI Coding Agent

**Document type:** Planning / architecture discovery brief  
**Project:** Restaurant Operations Management System (ROMS)  
**Current instruction:** Inspect and report first. Do not implement or modify code in this task.

---

## 1. Your role and objective

Act as the repository analyst and architecture reviewer for ROMS. The goal is to inspect the current codebase and produce a practical, evidence-based proposal for evolving it into a multi-tenant restaurant operations SaaS with three clearly separated user experiences:

1. **Platform Admin** — the internal console used by the ROMS owner/company to manage all customer businesses and outlets.
2. **Business Admin** — the authenticated management application used by a restaurant owner and their authorised staff.
3. **Customer Website / Digital Menu** — the public, restaurant-branded website opened by a guest, usually after scanning an outlet's QR code.

These experiences have different users, permissions, navigation, workflows and visual needs. They should not become one tangled UI with many conditional screens. At the same time, the project should not duplicate backend business logic or create a separate backend/database for each UI.

The intended direction is **three independently organised frontend applications sharing one backend API, one source of truth in PostgreSQL, and shared infrastructure**. This is a target to evaluate against the actual repository, not permission to restructure it immediately.

Your task in this phase is to understand the existing implementation, identify gaps and risks, and recommend an incremental migration/implementation plan. Do not assume the repository matches this document exactly; verify all details in code and report what is actually present.

## 2. Business context and product vision

ROMS is being developed initially for a family restaurant business in Himachal Pradesh. The business has two outlets around 40–60 minutes apart and the outlets have different restaurant formats/menus. One is a more traditional restaurant that may already use printed menus and billing software; another is a busy riverside camp restaurant where proper order/billing workflows are more urgently needed. There is also an operational concern about customers leaving without paying and the owner needing timely order/sales visibility.

The long-term goal is not just a QR menu. ROMS may become a SaaS product for multiple restaurant businesses, each with one or more outlets.

High-level product direction:

- Start with a reliable digital menu and the ability to manage its content.
- Add restaurant-owner/staff operations such as orders and kitchen workflows.
- Add customer ordering and billing/payment features later.
- Add platform-level tenant management, subscriptions and SaaS operations.
- Keep the architecture understandable and cost-conscious until real usage proves that more complexity is needed.

Do not introduce microservices, Redis, Kafka, or other infrastructure without a specific measured need. Prefer a modular monolith and clear module boundaries.

## 3. Current known technology and constraints — verify in the repository

Known context from prior project work:

- Frontend: React + Vite + TypeScript.
- Backend: FastAPI.
- ORM: SQLAlchemy 2.x.
- Migrations: Alembic.
- Database: Neon PostgreSQL (region chosen: AWS Asia Pacific / Singapore).
- Object storage for restaurant logos and food images: Cloudflare R2.
- Backend upload integration is expected to use Python `boto3` / S3-compatible API.
- Existing initial migration is believed to be `0001_initial_r1_schema.py`.
- Existing domain models are believed to include `Business`, `Outlet`, `MenuCategory`, and `MenuItem`.
- QR scan → customer menu flow is already working.
- A business/admin application has begun to be implemented, but the exact completion and current authentication state must be verified.
- A separate image storage implementation document exists or is planned: `ROMS_R2_Image_Storage_Implementation.md`. If it exists in the repo, inspect it and compare it with the code.

The exact repository structure, route names, authentication mechanism, deployment setup and current feature status are unknown until inspected. Do not invent them.

### Project constraints

- Do not make production/deployment/infrastructure changes without explicit approval.
- Do not apply database migrations or alter live data in this audit phase.
- Do not expose or request credentials/secrets. Do not print environment secret values into reports.
- Preserve the working QR/menu flow.
- Avoid unnecessary refactors purely for code aesthetics.
- Do not implement features in this task.
- Do not run the full test suite simply as part of the audit unless the current project instructions or an important discovery makes it necessary. If tests are needed to establish baseline health, explain why first and run the smallest relevant checks.

## 4. Core architecture principle

**Separate the three user experiences; share the backend and domain logic.**

Target logical structure:

```text
ROMS repository (potential target, not a required immediate restructure)
├── apps/
│   ├── platform-admin/   # Internal ROMS company console
│   ├── business-admin/   # Restaurant owner/manager/staff application
│   └── customer-web/     # Public, multi-tenant restaurant website/menu
├── packages/
│   ├── shared-types/     # Shared API/domain types where appropriate
│   ├── api-client/       # Shared API client/configuration where appropriate
│   ├── validation/       # Reusable schemas only where suitable
│   └── ui/              # Optional reusable primitives, not shared page layouts
└── backend/              # FastAPI application, domain modules, migrations
```

This is a conceptual example. Inspect the current repo before recommending whether to adopt this exact layout, use workspace tooling, or migrate gradually. Avoid a large folder move unless it has a clear benefit and a safe sequence.

### Important distinction

- **Separate frontend applications:** independent entry points, route trees, layouts, navigation, and potentially build/deployment targets.
- **Shared backend:** one FastAPI service and domain logic, with role- and tenant-aware API access.
- **Shared data:** one Neon PostgreSQL database as the source of truth.
- **Shared storage:** Cloudflare R2 for public menu images/logos, using object keys in the database.
- **Shared packages:** only genuinely reusable pieces such as types, API utilities, validation schemas and low-level UI primitives. Do not force the three applications to share entire pages, navigation or visual design.

Three separate frontends do **not** require three separate backend services.

## 5. The three applications and their responsibilities

### A. Platform Admin — internal ROMS/company console

Primary users: ROMS owner and explicitly authorised platform administrators.

This is a privileged control plane for the SaaS platform. It should not be exposed as a normal restaurant-owner dashboard.

Expected capabilities over time:

1. Dashboard: total businesses, outlets, account states and recent activity.
2. Business directory: search/filter all businesses, inspect a business, create a business, edit details, activate/suspend according to policy.
3. Outlet management: add outlets to a business, edit outlet details, view outlet status and configuration.
4. Menu setup/support: create or manage categories and menu items on behalf of a business/outlet where permitted; upload logos and food images; support editing and archive/deletion workflows.
5. QR management: create/resolve the outlet's public menu URL, generate a QR code, preview it and download a print-ready image/PDF if supported.
6. Platform account management: associate business owners/managers with the correct business and outlets, invite/reset access through a safe workflow as appropriate.
7. Subscription administration: initially it may be enough to assign a plan and manage trial/active/past-due/cancelled status manually. Real recurring payment collection, invoices, payment webhooks and automated renewals are later work.
8. Platform settings and support tools, only when needed.
9. Audit history for sensitive operations, such as suspending a business, changing a plan, deleting/archiving menu content, or changing access.

Platform admin should have cross-tenant access only through explicit platform-admin authorization. Do not grant it merely because a frontend route is named `/platform`.

### B. Business Admin — restaurant management app

Primary users: business owners, managers and authorised staff.

A business user should only see/manage the business and outlets to which their account has access.

Expected capabilities, delivered incrementally:

1. Sign in and view the business/outlets they are authorised to access.
2. Manage outlet details and settings within their role.
3. Create/edit categories and menu items, set prices/descriptions/availability, upload images and publish menu changes.
4. Manage outlet branding settings where permitted, within safe supported options.
5. View/generate/download outlet QR codes where that is part of the customer plan and permissions.
6. Later: staff management, order entry, kitchen display, order status, bills/payments, sales summaries and reporting.

The business admin should not be able to list all platform businesses or access another business by changing an ID in a request.

The precise business-admin scope should be compared with the current implementation. Do not build all future operational modules now.

### C. Customer Website — public multi-tenant branded menu

Primary users: restaurant guests, usually arriving through an outlet QR code.

This should be one reusable website engine, not a separate codebase/deployment for every restaurant.

Expected behaviour:

1. Guest scans an outlet QR code or opens its stable public URL.
2. The website resolves the business/outlet using a stable outlet slug or identifier.
3. It requests the outlet's published public configuration and menu from the backend.
4. The website applies the permitted branding settings and renders the menu.
5. The guest sees only public, published content for that outlet.
6. Later, the same experience may add customer ordering and payments.

Restaurant A and Restaurant B may use the same frontend code but have different logos, cover images, colours, category names/order, menu items, photos, prices and outlet information.

Example illustrative URLs:

- `menu.example.com/riverside-camp`
- `menu.example.com/hillside-dhaba`

Do not assume these domains or route structures are already configured. Preserve the current working QR URL scheme unless a migration is justified.

Later, custom domains may be considered for eligible customers, but they are not required for the first implementation.

## 6. Restaurant branding and tenant-specific configuration

The customer website must support database-driven branding. The brand is configuration/data, not hardcoded per restaurant in frontend code.

Possible settings (verify existing schema before proposing new fields):

- Business logo.
- Optional outlet-specific logo override.
- Cover/banner image.
- Primary, secondary/accent, background and text colours.
- Supported font choice or typography preset.
- Supported visual template/layout choice, if multiple layouts are introduced.
- Category visibility, display order and category labels.
- Menu item visibility/order and item-specific content.
- Restaurant/business name, outlet name, address, contact information and opening information as appropriate.
- Optional short description or announcement.

Recommended ownership concept:

- Business-level branding provides defaults.
- An outlet can override selected values when outlets need distinct branding.
- Menu data must be assigned to outlets deliberately. Do not assume every outlet of a business has the same menu.
- Initially, one high-quality menu layout with configurable branding is likely enough. Do not build a full theme/template marketplace prematurely.
- Validate supported colour formats and template/font options. Never allow arbitrary user-provided HTML, JavaScript or CSS to execute.
- Public APIs should return only customer-visible fields and published content.

The agent should recommend a clear model for business defaults versus outlet overrides and identify where the current schema needs changes. Do not make schema changes in this task.

## 7. Tenant and data model principles

Inspect the current ORM models, foreign keys, constraints and migrations. At minimum, reason about these domain concepts:

- Business / tenant.
- Outlet belonging to a business.
- Menu category and menu item, with explicit business/outlet ownership or assignment.
- User identity and business/outlet membership.
- Roles/permissions.
- Branding/configuration.
- QR/public outlet identifier or slug.
- Subscription plan and subscription/account status.
- Image object keys.
- Future order, order-item, payment/billing and audit records.

Do not create every future table now. Separate what is necessary for the current phase from future domain concepts.

Questions to answer from code inspection:

- Are menu categories/items associated with a business, an outlet, or both?
- Can two outlets have different menus?
- Is the public slug unique and stable?
- What happens if an outlet is renamed or disabled?
- How is the current QR URL generated, stored or resolved?
- Are there unique constraints and indexes for public lookup and tenant scoping?
- Can business users be associated with multiple outlets?
- Is there any authentication or role model already implemented?
- Does the existing schema support business-level branding plus outlet overrides, or would it need an additive migration?
- Are deletions hard deletes, soft deletes/archival, or not implemented?

Be specific about what exists and what is only a recommendation.

## 8. Backend/API principles

Use one FastAPI backend, organised into understandable domain modules/router groups. Separate endpoint namespaces by purpose where helpful, for example:

- `/api/platform/...` for platform administration.
- `/api/business/...` for authenticated business operations.
- `/api/public/...` for public menu/configuration reads.

These are illustrative names, not mandatory endpoint names. Reuse domain/service logic instead of implementing different copies of the same operation for each frontend.

Illustrative endpoint concepts:

- List/create/update businesses.
- List/create/update outlets under a business.
- List/create/update/archive menu categories and items.
- Read a published outlet menu and its public branding.
- Upload/replace/delete menu images under authorised rules.
- Generate or resolve QR information.
- Assign and inspect subscription plan/status.

The agent should map these concepts to the current API and propose missing endpoints; it must not create them during this audit.

### Security requirements

Authorization must be enforced by the backend on every protected request. Hiding buttons or routes in React is not security.

- Platform routes require an explicitly authorised platform-admin role.
- Business routes require authentication plus a verified membership/role for the relevant business/outlet.
- Never trust a client-supplied `business_id` or `outlet_id` without checking the user's permission for it.
- Public routes expose only published public fields and content.
- Avoid insecure default admin accounts or hardcoded credentials.
- Recommend a safe first-platform-admin provisioning method based on the current authentication setup.
- Record sensitive administrative actions in an audit trail when appropriate.
- Keep secrets in environment configuration; never place R2 credentials or database secrets in frontend code.
- Consider rate limiting/abuse protections for public endpoints where appropriate, but do not add infrastructure without need.

## 9. Cloudflare R2 image storage

Known intended approach:

- Use Cloudflare R2 for food images, logos and other public customer-menu assets.
- Use backend-mediated uploads through authenticated FastAPI endpoints initially.
- `boto3`/S3-compatible access is used by the backend, never by browser code.
- The backend validates the user, business/outlet permissions, file size, file type/content and upload constraints.
- Store the **R2 object key** in PostgreSQL, not a complete URL and not a time-limited presigned URL for public images.
- The public API derives the image URL from a configured public base URL and the stored object key.
- The browser loads public images directly from the R2 public URL/custom domain, not through FastAPI as a proxy.
- Use the exact Cloudflare-provided `r2.dev` base URL for temporary development if the public development URL is enabled. Do not manually guess or construct a `r2.dev` hostname.
- A custom domain can replace the public base URL later without changing stored object keys.
- `r2.dev` is for development/testing, not the production delivery strategy.
- Do not expose secrets in logs or reports.

Known bucket details from user context:
- Bucket: `roms-public-images`.
- Region/location: APAC.
- S3 API endpoint was shown as `https://7425b783f2729110adc54a55d8148b97.r2.cloudflarestorage.com/roms-public-images`.
- Public Development URL was initially disabled; user planned to enable it.
- No custom domain was configured at the time this context was recorded.
- Never assume the development URL has been enabled or infer its exact public base URL. Read configuration names and documentation without printing secrets.

Inspect the current implementation and the image-storage planning document if present. Report gaps such as unsafe file validation, blocking synchronous upload calls inside async request handlers, incorrect URL construction, missing authorization, unsafe delete/replacement behaviour, missing orphan cleanup strategy, or lack of tests. Do not implement fixes in this task.

## 10. QR code strategy

The QR code should point to a stable public outlet URL, not embed the menu JSON or images.

Expected flow:

1. An outlet has a stable public slug/identifier.
2. The system builds its canonical public menu URL.
3. A QR generator encodes that URL.
4. Platform/business admin can preview and download the QR.
5. Menu edits do not require a new QR because the URL remains stable.
6. If a slug must change, plan redirects or a deliberate QR replacement strategy rather than silently breaking printed QR codes.

Clarify whether QR images should be generated on the frontend or backend based on the existing code and requirements. There is no need to store a QR image permanently if it can be deterministically generated from the stable URL, unless a real requirement justifies storage.

## 11. Subscriptions and billing

Platform-level subscription management is a planned capability, but do not implement payment processing in this task.

Plan the stages:

**Stage 1 — manual administration**
- Plan assigned to a business.
- Subscription status and trial/renewal dates where relevant.
- Platform admin can view and update status.
- A clear audit trail for plan/status changes.

**Stage 2 — enforce entitlements**
- Define which features are available on each plan.
- Enforce entitlements in the backend, not just by hiding UI controls.
- Decide what happens when a subscription expires or a business is suspended without unexpectedly deleting its data.

**Stage 3 — payment automation later**
- Payment provider integration, invoices/receipts, webhook verification, renewals, retries and reconciliation.
- This should be designed when a provider and business requirements are known.

Do not build a fake automated billing experience. Distinguish manual status administration from real payment collection.

## 12. Deployment and domain separation

Possible future hostnames, only as examples:

- `platform.<domain>` — platform admin.
- `app.<domain>` — business admin.
- `menu.<domain>/<outlet-slug>` — customer website.
- `api.<domain>` — FastAPI API.

The applications can be deployed independently from one repository. A customer-web styling release should ideally not require deploying the platform-admin application. The backend may initially be one deployment.

Inspect the actual current hosting and deployment configuration before recommending a migration. Do not change DNS, Cloudflare Pages/Workers, backend hosting, Neon settings, R2 settings or production deployment in this task.

For the customer website, consider:
- How a URL/slug resolves to a tenant/outlet.
- Cache keys that include the correct tenant/outlet.
- Avoiding one outlet's menu/branding being served to another outlet.
- Publishing and cache invalidation behaviour.
- CORS and authentication needs for each frontend origin.
- Custom domains only as a later optional capability.

Do not introduce SSR or a new rendering architecture unless there is a demonstrated requirement. Assess the existing React/Vite setup and public-menu needs first.

## 13. Suggested phased roadmap

This is a proposed roadmap to evaluate, not a mandate to implement all phases immediately.

### Phase 0 — repository audit and architecture decision (this task)
- Inspect code, docs, tests, migrations and configuration names.
- Map current features and the working QR/menu flow.
- Identify frontend/backend boundaries.
- Inspect authentication and tenant authorization.
- Recommend app separation strategy and migration plan.
- No code changes.

### Phase 1 — secure platform foundation
- Establish safe platform-admin authentication/provisioning.
- Add platform business directory and create-business workflow.
- Add outlet creation and management.
- Reuse existing business/outlet services.
- Add focused authorization and CRUD tests.

### Phase 2 — menu and image administration
- Platform admin can manage categories/items for a chosen business/outlet.
- Implement or complete backend-mediated R2 image upload and URL generation.
- Add edit/archive/delete workflows and upload tests.
- Ensure outlet-level menu differences are supported.

### Phase 3 — multi-tenant customer website configuration
- Customer website resolves outlet and fetches published configuration/menu.
- Apply database-driven branding and category ordering.
- Preserve existing QR behaviour and public URL compatibility.
- Add tenant-isolation tests and check caching assumptions.

### Phase 4 — business-admin separation and permissions
- Give restaurant owners/managers their own application experience.
- Restrict data by membership, role and outlet assignment.
- Reuse the backend domain services and shared low-level packages.

### Phase 5 — QR management and operational modules
- QR preview/download.
- Later add order management, kitchen display, billing/payment and sales reporting in a sequence guided by actual restaurant needs.

### Phase 6 — subscriptions and SaaS operations
- Manual plan/status administration.
- Entitlement enforcement.
- Payment automation only after requirements/provider selection.

The phases can be adjusted based on what is already implemented. Do not assume phase 1 must restart from scratch.

## 14. Testing and quality expectations

During this audit, inspect existing test setup and coverage rather than changing code.

For any later implementation plan, include tests for:

- Platform admin authorization and forbidden access for non-platform users.
- Business A cannot read or mutate Business B's protected data.
- Outlet manager cannot access an unassigned outlet.
- Public menu exposes only published/public fields.
- Business/outlet/category/item relationships are validated.
- Slugs/QR URLs remain stable and resolve to the correct outlet.
- Branding configuration has valid supported values and correct fallback precedence.
- Images upload to the intended key, URL is built correctly, invalid files are rejected, and unauthorised users cannot upload/delete.
- Deleting/replacing an image doesn't leave the database pointing at a missing object; failure modes are handled.
- Tenant-aware cache behaviour, if caching is used.
- Subscription entitlements, once implemented.

Use the smallest relevant test suite during implementation. Run the full suite only at task completion or when a shared/global change makes it necessary. For this current audit, do not run the full suite without a specific reason.

## 15. What I want you to do now

Perform a **read-only repository audit** and return a structured report. Do not implement, refactor, create files, change configuration, or run migrations.

Inspect the relevant frontend and backend code, models, migrations, routers, authentication/authorization, QR/menu flow, R2 image flow, tests, and existing project documentation. If a detail is unclear, search the repository and report uncertainty rather than guessing.

### Required report sections

1. **Executive summary** — current state and recommended direction in plain language.
2. **Verified current architecture** — actual repository layout, frontend entry points, backend modules, database/storage and deployment information found in repo. Distinguish verified facts from unknowns.
3. **Current feature inventory** — what is implemented, partially implemented, missing or unclear for each of the three interfaces.
4. **Existing QR → public menu flow** — trace the actual code path from QR/public URL through API/data lookup to menu rendering.
5. **Data model and tenant isolation review** — current entities, relationships, constraints, missing relationships, and cross-tenant risks.
6. **Authentication and authorization review** — existing mechanisms and the safest practical platform-admin provisioning path.
7. **Branding/configuration review** — how logo, images, colours, category order/visibility, business defaults and outlet overrides should fit the existing model.
8. **R2 integration review** — current upload/storage/public URL approach and gaps against the intended design. Do not reveal secret values.
9. **Proposed frontend separation** — whether to use three app folders/builds now, an incremental extraction, or another justified approach. Include a proposed directory tree based on the actual repo.
10. **Proposed API boundaries** — current route groups and suggested missing endpoint concepts, without implementing them.
11. **Database changes likely needed** — additive migration concepts only; do not create migrations.
12. **Deployment considerations** — based on current config; no infrastructure changes.
13. **Security, reliability and operational risks** — prioritised by severity and practical impact.
14. **Phased implementation plan** — small, ordered tasks with dependencies and acceptance criteria.
15. **Testing plan** — minimal targeted tests per phase and when full tests should run.
16. **Open decisions/questions** — only decisions that genuinely need product-owner input; make a recommendation where possible.
17. **Recommended next step** — one concrete next task, not a giant implementation prompt.

### Evidence and reporting requirements

- Cite file paths and relevant symbols for every major claim (e.g. router, model, component, migration, test).
- Mark each important statement as one of:
  - **Verified in code**
  - **Inferred**
  - **Not found / needs confirmation**
- Do not claim something exists because it is mentioned in this document.
- Call out inconsistencies between the repository and this plan.
- Prefer a practical minimal migration over a rewrite.
- Be candid if the current structure already supports some of this and a large refactor is unnecessary.
- Avoid generic architecture advice that does not map to the repository.
- Do not modify any files in this task.
- Finish with the smallest sensible next implementation step and its acceptance criteria.

## 16. Decision principles

Use these principles when evaluating options:

1. Separate the three UIs because their users, navigation, permissions and responsibilities differ.
2. Keep one shared FastAPI backend and one PostgreSQL source of truth.
3. Treat the customer website as a multi-tenant theme/configuration-driven engine, not one deployment per restaurant.
4. Enforce tenant access on the backend for every protected operation.
5. Keep the current QR/menu flow working and avoid breaking printed QR codes.
6. Store R2 object keys in the database; generate public image URLs from configured base URL; do not expose R2 credentials to browsers.
7. Prefer additive schema changes and incremental extraction.
8. Do not build payment automation, multiple themes, custom domains or future ordering workflows prematurely.
9. Do not introduce additional infrastructure without evidence that it is needed.
10. Audit first, propose next, implement only after the owner reviews and approves the plan.

**End of brief.**
