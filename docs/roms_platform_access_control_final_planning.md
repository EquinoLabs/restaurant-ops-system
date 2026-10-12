 ROMS Platform Access Control — Final Planning & Acceptance Baseline

  Baseline Document: platform-access-control-and-team-management.md (v1.9.0)
  Status: Implementation Progress & Acceptance Baseline (Phases 1–6 Formally Accepted & Closed)
  Preservation Confirmation: All 24 tracked modified files and 9 untracked files remain completely preserved in the working tree. Zero migrations
  run, zero databases accessed or mutated, zero Git commands executed.
  ──────
  ## 1. Corrected Planning Section: Bootstrap State-File Durability & Operational Coordination

  Because a database rollback wipes out all rows inserted within that transaction, the bootstrap_run_id cannot rely on uncommitted database state to survive an aborted transaction. Furthermore, volatile in-
  memory filesystems (such as /run or /var/run on Linux systems, which mount tmpfs) do not survive machine reboots.

  ### 1.1 Implementation-Design Requirement: Persistent Storage Location

  The future implementation design must select a deployment-appropriate, non-volatile persistent storage location based on the target deployment environment (e.g., dedicated administrative state directory
  on persistent volume storage, rather than temporary or volatile paths). Selecting a hardcoded path without full deployment context is deferred to authorized implementation design.

  The persistent storage design must satisfy five operational criteria:

  1. Persistence Across Process Termination & Machine Restarts:
  The execution record must be written to non-volatile disk storage before initiating the database transaction. If the CLI process is killed, the terminal closes, or the host machine reboots while commit
  status is unacknowledged, the state record remains intact and readable upon system restart.
  2. Protection Against Unauthorized Access or Tampering:
  The file and directory must enforce restrictive filesystem permissions (e.g., 0600 / administrative service owner only). Unprivileged OS users, application workers, and web server processes cannot read,
  alter, or delete bootstrap execution records.
  3. Safe Coordination of Concurrent CLI Invocations:
  To coordinate multiple administrative sessions or operators on the same host, the CLI process must acquire an exclusive host-level coordination lock (e.g. OS file lock) alongside the PostgreSQL
  transactional advisory lock 424242111. If two operators invoke the CLI concurrently, the second process is blocked at both the host and database engine levels.
  4. Deterministic Recovery Using Original bootstrap_run_id:
  If a bootstrap execution experiences an ambiguous outcome (e.g., network drop awaiting commit confirmation), the operator retrieves the durable bootstrap_run_id from the persistent state file and invokes
  the CLI with --reconcile-run-id=<UUID>. The reconciliation routine queries PostgreSQL specifically for that run ID under advisory lock 424242111.
  5. Mandatory Reconciliation Precedent Before New Run IDs:
  An operator or automated script is strictly prohibited from generating a new run ID while an unresolved local run record exists. Reconciliation of the existing attempt must conclusively establish its
  outcome (Case 1: Succeeded or Case 2: Aborted) before the local state file can be archived and any new bootstrap attempt initiated.
  ──────
  ## 2. Corrected Planning Section: Safe Zero-Owner Governance & Recovery Isolation

  The architecture enforces a strict boundary between ordinary runtime governance operations and the narrowly authorized bootstrap/recovery path:

  ### 2.1 Ordinary Platform Governance Operations (Fail-Closed Invariant)

  During normal operations, the platform invariant requires exactly one active Platform Owner (count == 1). In any transitional state where active Owner count is zero:

  • All ordinary role-governance endpoints and service-layer functions (grant_platform_admin, revoke_platform_admin, create_platform_operator, revoke_platform_operator, transfer_platform_ownership, and
  account reactivation) invoke _assert_platform_owner_initialized and fail closed with HTTP 503 Service Unavailable.
  • This invariant guarantees that standard Platform Admins cannot exploit the absence of an Owner to self-promote, modify other Admins, or perform un-governed role mutations.
  • Ordinary commercial operations (POST /businesses, PATCH /subscriptions, POST /overrides) continue uninterrupted for Admins without weakening security boundaries.

  ### 2.2 Narrowly Authorized Bootstrap & Recovery Path

  The bootstrap procedure (bootstrap_initial_platform_owner) and any future emergency recovery path are decoupled from the ordinary service check:

  1. Explicit Operational Authorization:
  The bootstrap path cannot be executed arbitrarily or via public HTTP endpoints. It is restricted to a dedicated administrative CLI requiring explicit written stakeholder designation of the target user
  (DECISION-OP-04). Any emergency recovery protocol requires formal authorization under DECISION-OP-03.
  2. Revalidation Under Governance Serialization Protocol:
  The bootstrap procedure does not bypass security; it executes under the unified platform serialization lock (pg_advisory_xact_lock(424242111)). Under this lock, it revalidates all required invariants:
      • Verifies the designated target exists and holds status == 'active'.
      • Verifies the designated target is currently an active Platform Admin (platform_role == 'admin', is_platform_admin is True).
      • Verifies that zero active Owners currently exist before promoting.
      • Asserts post-promotion active owner count is exactly 1 before committing.
  3. Fail-Closed on Ambiguous or Contradictory State:
  If any condition fails, if the lock cannot be acquired, or if an audit record exists without an active Owner (or vice versa), the procedure aborts and rolls back completely.
  4. No General-Purpose Bypass:
  The bootstrap routine promotes strictly the designated target Admin to Owner and exits. It provides zero mechanism to modify arbitrary users, demote admins, or bypass OutletMembership tenant boundaries,
  ensuring zero general-purpose authorization bypasses exist in the system.
  ──────
  ## 3. Summary of Remaining Implementation-Design Limitations

  1. Proposed Schema Dependency (idempotency_records): The idempotency_records table does not exist in schema 0010. Creating this table and its constraints represents proposed Phase 2 schema work to be
  reviewed and migrated during authorized implementation.
  2. Deployment-Specific Storage Path: Selecting the non-volatile persistent directory for bootstrap state records requires environment and infrastructure context (e.g. host OS, container volume mount) and
  is recorded as an implementation-design deliverable.
  3. PostgreSQL Concurrency Integration Testing: Verifying advisory lock serialization (424242111), partial unique index enforcement (uq_users_single_active_owner), and ON CONFLICT row locking requires an
  active PostgreSQL test instance and cannot be validated against SQLite.
  ──────
  ## 4. Decision Register Status (OP-01 through OP-05)

  All five product decisions remain strictly open. Technical planning does not infer approval of any option:

  • DECISION-OP-01 (Operator Onboarding Flow): OPEN. (Blocks Phase 5 Operator provisioning).
  • DECISION-OP-02 (Ownership Transfer Protocol): OPEN. (Blocks Phase 3 Transfer Service coding).
  • DECISION-OP-03 (Emergency Break-Glass Protocol): OPEN. (Blocks Operational Recovery Runbooks).
  • DECISION-OP-04 (Initial Owner Identity Selection): OPEN. (Blocks Stage 7 Owner Bootstrap execution).
  • DECISION-OP-05 (Tenant Subscription Inspection): OPEN. (Blocks Tenant-facing Subscription routes).
  ──────
  ## 5. Phase 6 Formal Acceptance & Closure (Business & Outlet Profile Management)

  Phase 6 (Business & Outlet Profile Management) and its targeted security remediation were formally accepted and closed on 2026-10-13 based on full test passing and authorization audit PASS verification.

  ### 5.1 Scope & Approved Decisions Delivered
  • Decision D-01 (Option A): Business name profile updates restricted to Platform Owners and Admins; Platform Operators attempting mutations are denied with HTTP 403 Forbidden. Outlet profile updates are accessible to Owners, Admins, and Operators.
  • Decision D-02 (Option B): Scoped strictly to profile metadata and branding colors (primary_color, accent_color). Zero binary image uploads, logo/cover file flows, or R2 mutations.

  ### 5.2 Security Findings Remediated
  • Finding M-01 (API Response Commercial Data Exposure): Resolved via role-scoped response schema serialization. GET /api/v1/platform/businesses/{business_id} serializes PlatformBusinessProfileOut for Operators, strictly omitting subscription_status, plan_name, max_outlets, and trial_ends_at. Owners, Admins, and valid legacy Admins receive full PlatformBusinessOut. Invalid non-null roles and unauthorized callers fail closed.
  • Finding L-01 (Frontend Card & Tab Visibility): Resolved via fail-closed isAuthorizedCommercial guard in OutletDetailDrawer.tsx. Commercial subscription badge, Plan Tier card, Outlet Capacity card, Trial Status card, and commercial tab views are completely hidden from Operators.

  ### 5.3 Verification & Audit Status
  • Full Backend Test Suite: 138 / 138 tests passing (100% pass rate across 15 test modules).
  • Full Frontend Test Suite: 76 / 76 tests passing (100% pass rate across 9 test suites).
  • Role-scoped business response schemas, Operator commercial-data restrictions, and frontend fail-closed behavior are fully covered by automated regression tests.
  • Final Read-Only Authorization Audit: Reported PASS across all 6 verification criteria.

  ### 5.4 Database & Migration Boundary
  • Draft Migration Unapplied: Migration 0011_add_platform_role_column.py remains an unapplied draft script.
  • Zero Database Migrations / Schema Changes: Applied migration head remains 0010_subscription_entitlements_schema.py. Zero live databases were accessed or mutated.

  ──────
  ## 6. Confirmation of Execution Boundaries

  In strict compliance with governance rules:

  • Documentation-only closure: Zero changes to application code, tests, configuration, schemas, or migrations during closure.
  • Working Tree Preservation: All 24 tracked modified files and 9 untracked files remain completely preserved in the working tree.
  • Zero Database Operations: Zero migrations executed; zero live databases connected to or mutated.
  • Zero Git Actions: Zero Git commands run (commit, stage, push, revert, discard, stash, checkout).
  • Decision Register: Decisions OP-01 through OP-05 remain strictly OPEN.
  • Phase 7 Boundary: Phase 7 is NOT authorized or started. Standing by for stakeholder instructions.
