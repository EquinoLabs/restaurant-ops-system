# ROMS Operational Runbook: Emergency Break-Glass Recovery Protocol (OP-03)

**Document ID:** ROMS-RUNBOOK-GOV-03  
**Status:** Approved & Implemented (DECISION-OP-03 Option A)  
**Classification:** Restricted Administrative Runbook  
**Target Architecture:** ROMS Three-Tier Access Control & Platform Governance  

---

## 1. Purpose & Scope

This runbook defines the emergency break-glass procedure for restoring ROMS Platform Owner access when normal governance workflows become unavailable (e.g., Platform Owner incapacitation, credential loss, account compromise, or orphaned governance).

### Distinction: Initial Bootstrap vs Break-Glass Recovery

| Attribute | Routine Initial Bootstrap (`create_platform_admin.py`) | Emergency Break-Glass Recovery (`break_glass_recovery.py`) |
| :--- | :--- | :--- |
| **Operational Context** | Greenfield environment setup / deployment Stage 7. | Documented production incident (P1/P2 disaster recovery). |
| **Pre-Condition** | 0 active Platform Owners exist prior to first bootstrap. | Existing Owner incapacitated, suspended, compromised, or orphaned. |
| **Trigger** | Initial release orchestration script. | Human incident commander / authorized operations lead. |
| **Authorization Gate** | Stakeholder written designation (DECISION-OP-04). | Mandatory incident reference (`--incident-ref`) + operator ID (`--operator`). |
| **Safety Gating** | Direct write execution. | Read-only diagnostic Stage A, dry-run Stage B, `--confirm` required for Stage C. |
| **Audit Logging** | Local script stdout output. | Transactional platform audit log (`platform.recovery.break_glass`). |
| **Owner Replacement** | Rejects if an active owner already exists. | Atomically demotes previous owner to admin and elevates designated successor admin. |

---

## 2. Invariants & Safety Boundaries

1. **Restricted Shell Execution:** Recovery is executable only through direct server shell access to `backend/scripts/break_glass_recovery.py`. There are **no public or application-level recovery endpoints**.
2. **Explicit Target Environment Selection:** Recovery strictly requires `--target-env` (`production`, `staging`, `development`, `local`, `test`). The CLI verifies configuration before opening a database session. Implicit fallback to localhost default configuration in production or staging is strictly prohibited and fails closed.
3. **Mandatory Attribution & Incident Format:** Every write execution requires `--operator` and `--incident-ref` matching pattern `^(INC|CHG|ROMS)-<digits>` (e.g. `INC-48201`, `CHG-1002`, `ROMS-1234`). Non-matching or missing attribution fails closed immediately. Supplementary OS user and host context are recorded for forensic correlation.
4. **Dry-Run Default:** Any execution omitting `--confirm` acts as a read-only dry run (Stage B) and will not mutate database state.
5. **Single-Active-Owner Upper Bound ($\le 1$):** At no point may the recovery tool allow two active Platform Owners. An existing active Owner is demoted to `admin` before the successor is promoted.
6. **Single-Active-Owner Lower Bound ($\ge 1$):** Post-recovery assertion verifies that active Owner count is **exactly 1**. If not, the transaction rolls back immediately with `RuntimeError`.
7. **Strict Target Eligibility & Disabled Operations:**
   - For `replace-owner`: Target must exist, be `status == 'active'`, and hold `platform_role == 'admin'` and `is_platform_admin is True`. Arbitrary users or operators cannot be elevated directly to Owner.
   - For `reactivate-owner`: Target must be an existing Owner whose status is `suspended`, and 0 active owners must exist.
   - **`reset-credentials` is DISABLED:** Emergency credential reset via CLI is intentionally disabled due to command-line password exposure risks (`ps aux`, shell history) and stateless JWT invalidation limits. To recover access for a locked-out platform, use `replace-owner`.
8. **Advisory Locking:** All operations acquire PostgreSQL advisory lock `424242111` (`_acquire_admin_serialization_lock`).
9. **Data & Membership Preservation:** Tenant memberships (`OutletMembership`), subscriptions, outlet profiles, and unrelated accounts are never modified.
10. **Zero Secret Leakage:** Passwords, hashes, and tokens are never accepted via CLI flags or written to audit logs, stdout, or execution state.

---

## 3. Four-Stage Operational Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE A: DIAGNOSE (Read-Only Inspection)                               │
│ python backend/scripts/break_glass_recovery.py --target-env <env>      │
│   --diagnose                                                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE B: AUTHORIZE & DRY-RUN (Preflight Validation)                    │
│ --target-env <env> --action <act> --operator <op> --incident-ref <inc> │
│ --target <user> (Without --confirm)                                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE C: RECOVER (Atomic Transaction under Advisory Lock)              │
│ Append --confirm to execute write mutation                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE D: VERIFY & CLOSE (Governance Health Re-Validation)              │
│ Assert active_owner_count == 1; test login & API routes;               │
│ document incident record; close ticket                                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Stage A — Diagnose (Read-Only)

Connect to the application server and run the diagnostic command with explicit target environment:

```bash
python backend/scripts/break_glass_recovery.py --target-env production --diagnose
```

#### Status Interpretation
- **`HEALTHY`**: Exactly 1 active Platform Owner exists. If the Owner is reachable, break-glass is **not authorized**; use standard API governance.
- **`ZERO_OWNER_ORPHANED`**: 0 active Owners exist and no suspended Owner exists. Break-glass `replace-owner` is required to designate an active Admin as Owner.
- **`OWNER_SUSPENDED`**: 0 active Owners exist, but 1 suspended Owner exists. Use `reactivate-owner` (if accidental suspension) or `replace-owner` (if Owner departed/compromised).
- **`ANOMALOUS_MULTIPLE_OWNERS`**: More than 1 active Owner detected (database corruption/constraint bypass). **DO NOT EXECUTE AUTOMATED RECOVERY.** Immediately escalate to Lead Database Architect.

---

### Stage B — Authorize & Dry-Run

Obtain approval from the Incident Commander. Validate the proposed changes without writing to the database:

#### Example: Proposing Owner Replacement
```bash
python backend/scripts/break_glass_recovery.py \
  --target-env production \
  --action replace-owner \
  --operator "alex.lead@equinolabs.com" \
  --incident-ref "INC-48201" \
  --target "designated_admin@company.com"
```

Verify in the output:
- Target user ID and email are correct.
- Target user holds `platform_role='admin'` and `status='active'`.
- Notice states: `Dry-run completed successfully. Zero changes were written. Provide --confirm to execute recovery.`

---

### Stage C — Execute Recovery Operation

Once authorized and verified in Stage B, append `--confirm` to execute the transaction:

#### Scenario 1: Replacing an Incapacitated / Departing Platform Owner
```bash
python backend/scripts/break_glass_recovery.py \
  --target-env production \
  --action replace-owner \
  --operator "alex.lead@equinolabs.com" \
  --incident-ref "INC-48201" \
  --target "designated_admin@company.com" \
  --confirm
```

> [!WARNING] Operational Notice on Owner Replacement & Predecessor Access
> Replacing a Platform Owner atomically demotes the predecessor to active Platform Administrator (`platform_role = 'admin'`, `status = 'active'`).
> This prevents orphaned governance but **does NOT automatically revoke the predecessor's administrative access**.
> If Owner replacement was triggered due to **credential compromise, rogue insider threat, or hostile departure**:
> 1. Execute `replace-owner` to elevate the trusted successor Admin.
> 2. The new Owner must immediately log in and invoke the user-suspension API:
>    ```bash
>    POST /api/v1/platform/users/{predecessor_user_id}/suspend
>    ```
> 3. Suspending the predecessor account immediately invalidates all API access and existing authentication tokens (returning HTTP 401 Unauthorized on subsequent requests).
> 4. Verify that the new Owner remains active and governance health reports `HEALTHY` (1 active Owner).

#### Scenario 2: Reactivating an Accidentally Suspended Platform Owner
```bash
python backend/scripts/break_glass_recovery.py \
  --target-env production \
  --action reactivate-owner \
  --operator "alex.lead@equinolabs.com" \
  --incident-ref "INC-48202" \
  --target "existing_owner@company.com" \
  --confirm
```

#### Scenario 3: Credential Reset Is Unsupported (Disabled Protocol)
Emergency password reset via CLI (`reset-credentials` / `--new-password`) is intentionally **disabled and rejected by the CLI**. Passing `--action reset-credentials` or `--new-password` causes the CLI parser to reject the command before database initialization.

**Approved Alternative for Locked-Out Platforms:**
If the sole Platform Owner forgot their password or lost multi-factor access, an authorized operations lead must:
1. Coordinate with incident commanders to designate an existing trusted Platform Administrator.
2. Execute `replace-owner` (Scenario 1) targeting that Administrator.
3. The newly designated Owner logs in using their own existing credentials and manages platform operations.

---

### Stage D — Verify and Close

1. **Re-Run Diagnostic:**
   ```bash
   python backend/scripts/break_glass_recovery.py --target-env production --diagnose
   ```
   Confirm `Governance Status: HEALTHY` and `Active Owners: 1`.

2. **Verify API Governance:**
   Have the recovered/new Platform Owner log in via `/api/v1/auth/login` and query:
   ```bash
   curl -H "Authorization: Bearer <TOKEN>" https://<api-host>/api/v1/platform/businesses
   curl -H "Authorization: Bearer <TOKEN>" https://<api-host>/api/v1/platform/admins
   ```
   Both endpoints must return HTTP 200 OK.

3. **Verify Audit Trail:**
   Check the audit record in the database or via `/api/v1/platform/audit-logs`:
   - `action`: `platform.recovery.break_glass`
   - `metadata_json.operator`: Operator identity
   - `metadata_json.operator_system_user`: Operating-system user
   - `metadata_json.execution_host`: Host machine
   - `metadata_json.incident_ref`: Incident reference
   - `metadata_json.outcome`: `success`

4. **Credential Rotation Requirement:**
   If an emergency owner was designated, the new Owner must maintain strong credential hygiene.

5. **Close Incident:**
   Attach the recovery execution transcript and audit ID to incident ticket and mark closed.

---

## 4. Manual Escalation Procedure

If `break_glass_recovery.py` aborts with an error:
1. **Never attempt direct un-gated SQL updates** (e.g. updating roles without locks).
2. Contact the Platform Security Lead and Lead Database Architect.
3. Review PostgreSQL locks and connection pools:
   ```sql
   SELECT pid, query, state, age(clock_timestamp(), query_start) 
   FROM pg_stat_activity 
   WHERE query ILIKE '%users%';
   ```
4. Verify if advisory lock `424242111` is held by a hanging connection:
   ```sql
   SELECT * FROM pg_locks WHERE locktype = 'advisory';
   ```
