# ROMS Owner Decisions

**Purpose:** Record explicit product and business-policy decisions approved by the ROMS owner. These decisions guide implementation and resolve ambiguities in architecture documents.

## Decision Status

- **Proposed:** Awaiting owner approval.
- **Approved:** Explicitly approved by the owner.
- **Superseded:** Replaced by a later decision.

---

## Decision 001: Grant Scope Precedence

**Status:** Approved  
**Area:** Subscription Entitlements  
**Date:** 2026-10-11  

### Context

ROMS supports entitlement grants and restrictions at both business and outlet scope. The resolver needs deterministic rules when multiple overrides apply to the same feature.

### Decision

Option A — Hierarchical Scope Replacement

For a given target outlet and feature:

1. If one or more applicable active outlet-scoped grants exist, resolve grants using the outlet scope only.
2. Otherwise, resolve grants using applicable business-scoped grants.
3. When multiple numeric grants exist at the selected scope, use the highest numeric limit.
4. A grant with `limit_value = NULL` grants the capability but does not independently establish an unlimited numeric limit. If the selected scope has only null-limit grants, resolve the numeric limit through the documented plan, legacy restriction, and fallback rules.
5. An active restriction at either business or outlet scope overrides grants and denies the feature.
6. An outlet-scoped grant does not automatically increase the business-wide `outlets.max_count` creation allowance. Outlet-specific access and business-wide outlet creation capacity must be resolved separately.

### Related Policy

An outlet-scoped grant must not automatically increase the business-wide `outlets.max_count` creation limit. The implementation must distinguish granting access to a particular outlet from authorizing the creation of additional outlets.

### Implementation References

- `docs/architecture/roms_platform_admin_subscription_architecture.md`
- `docs/architecture/roms_platform_admin_implementation_roadmap.md`

### Approval Record

- Approved by: ROMS Owner  
- Approval date: 2026-10-11  
- Notes: Authorizes implementation of the documented precedence policy within Phase B. Does not authorize production migrations, deployment, or unrelated scope expansion.