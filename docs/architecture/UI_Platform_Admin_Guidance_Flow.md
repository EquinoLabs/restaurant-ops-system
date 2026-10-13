# ROMS Platform Admin Portal — End-to-End UI Flow Story

Think of the ROMS Platform Admin Portal as the internal control room for the entire ROMS SaaS platform. It is not the interface a restaurant owner uses to manage daily orders. It is where the ROMS platform team manages restaurant businesses, their outlets, platform access, subscriptions, plans, governance, and operational visibility.

The goal is to make every important administrative action follow a predictable story:

Open a section → view existing information → choose an action → review or enter information → confirm → see success or failure → verify the final state.

This is a functional blueprint for the intended final portal, including future features even if they are not built yet. It deliberately does not prescribe the visual layout.

## 1. The complete portal journey

Platform Admin signs in

Identity, authentication and platform-level permission check

Platform Overview

Understand the current state of ROMS and identify items needing attention

Businesses & Outlets

Create, inspect and manage restaurant tenants and their locations.

Users & Access

Inspect accounts, platform roles and access status.

Plans & Subscriptions

Define what customers can use and inspect their subscription state.

Audit & Governance

Understand who performed important actions and what changed.

Operational feedback

Clear outcomes, safe confirmations, permission errors, empty states and recovery paths

The major areas below describe the expected pages and the end-to-end behavior within them.

## 2. Sign-in, access and session flows

### 2.1 Platform Admin sign-in

1. The administrator opens the portal.
2. The portal checks whether a valid session already exists.
3. If a valid session exists, the administrator proceeds to the portal.
4. Otherwise, the sign-in screen appears.
5. The administrator enters their credentials and submits them.
6. Positive flow: credentials are valid and the account is authorized for platform administration; the administrator enters the portal.
7. Negative flow: credentials are incorrect; show a clear authentication error without revealing sensitive account details.
8. Unauthorized account: authentication succeeds, but the user is not a platform administrator; deny access to platform-admin pages.
9. Suspended account: reject access according to the platform's account-suspension rules.
10. Session expires: a protected action or page load discovers the expired session; ask the user to sign in again and avoid silently treating the action as successful.
11. Backend unavailable: show that the request could not be completed and allow a safe retry.
12. Repeated submission: prevent duplicate sign-in submissions while the current request is processing.

### 2.2 Permission checks throughout the portal

1. The administrator opens a page or attempts an action.
2. The portal checks access through the authoritative backend permissions.
3. Positive flow: the permission exists; continue.
4. Negative flow: the user is not authorized; deny the action and show an appropriate message.
5. Permission changed while the portal is open: the next protected request is denied if access has been removed.
6. Direct URL access: entering an admin URL manually must not bypass authorization.
7. Stale page state: if a record was accessible earlier but is no longer accessible, refresh or reload the relevant state instead of showing outdated data as authoritative.

## 3. Platform Overview / Dashboard

Purpose: Give the platform administrator a quick operational summary and useful paths into the rest of the portal.

### What the page contains

- Summary of registered businesses.
- Summary of outlets across the platform.
- Summary of users, where supported by the current backend.
- High-level subscription or plan status information, when that information is available.
- Important recent administrative activity.
- Items requiring attention, such as suspended businesses or accounts, if the system exposes those states.
- Shortcuts into frequently used administrative sections.

These are intended capabilities; exact metrics depend on the final backend data and business decisions.

### End-to-end flow

1. The administrator opens the dashboard.
2. The portal requests the overview information.
3. Positive flow: the summary loads and the administrator can open a relevant section from a metric or activity item.
4. No data yet: show zero values or a useful empty state instead of a broken dashboard.
5. Partial data failure: show which information could not load without implying that missing information means zero.
6. Complete request failure: show an error and a retry option.
7. Stale information: refresh the summary when appropriate; do not claim it is real-time unless the backend actually provides real-time updates.
8. Open recent activity: navigate to the relevant audit record or administrative section when a reliable destination exists.
9. Open business count: navigate to the business directory, optionally with the appropriate filter applied.

The dashboard is primarily for orientation and navigation. High-risk changes should still happen in their dedicated workflows.

## 4. Businesses section

Purpose: Manage the restaurant businesses registered on ROMS. A business is the tenant-level entity; it can own multiple outlets.

### 4.1 Business directory — viewing businesses

1. The administrator opens the Businesses section.
2. The portal loads the registered businesses.
3. Each result provides enough information to identify the business and understand its current status.
4. The administrator opens a business to view its details.
5. Positive flow: the directory loads and the selected business opens.
6. No businesses: show an empty state with an option to add the first business.
7. Search returns no results: explain that no businesses match the search.
8. Filters return no results: allow the administrator to clear or change filters.
9. Loading fails: show an error and retry option.
10. Business was removed, suspended or changed elsewhere: refresh its current state rather than relying on stale directory data.
11. Large directory: pagination or another appropriate loading mechanism lets the administrator browse all results without losing track of the current search or filters.

### 4.2 Add a business

1. The administrator opens the business directory.
2. They select Add Business.
3. A form or dedicated entry section opens.
4. The administrator enters the required business information.
5. They submit the form.
6. The portal validates the input and sends the request.
7. Positive flow: the business is created; show confirmation and make the new business accessible from the directory.
8. Validation error: explain which inputs need attention and preserve the entered values.
9. Duplicate or conflicting business: show the conflict and provide a way to review the existing record, where appropriate.
10. Permission error: explain that the administrator is not allowed to perform the action.
11. Backend or network error: show that creation did not complete, where known, and allow retry.
12. Uncertain outcome: if the request may have succeeded but the response was lost, check the directory before attempting to create the same business again.
13. Double-click or repeated submit: avoid creating duplicate businesses from the same submission.

### 4.3 View business details

1. The administrator selects a business.
2. The portal opens its detail view.
3. The administrator can inspect the business's core information, associated outlets, relevant users or memberships, subscription summary where supported, status, and available administrative actions.
4. They open an outlet or related record to inspect it further.
5. Positive flow: the details load and linked records lead to their own detail views.
6. Business not found: show a not-found state and return to the directory.
7. Partial data unavailable: clearly distinguish unavailable information from information that does not exist.
8. No outlets: show that the business has no outlets and provide an Add Outlet path if supported.
9. No related users: show an empty state rather than an error.
10. Stale information: refresh the record after a successful change or when the backend reports that it has changed.

### 4.4 Edit a business

1. The administrator opens the business details.
2. They choose Edit.
3. The editable information appears with the current values.
4. They change the required information and submit.
5. Positive flow: changes are saved and the details view reflects the updated information.
6. Validation error: preserve the form values and identify the issue.
7. Concurrent modification: if another administrator has changed the same record, avoid silently overwriting the newer values; reload and resolve the conflict.
8. No actual changes: avoid unnecessary writes or misleading success messages.
9. Save failure: retain the unsaved edits so they can retry.
10. Permission revoked: deny the update and refresh the affected state.

### 4.5 Business status and lifecycle

The portal should make business status visible and support only the lifecycle actions that the backend and business policy permit.

1. The administrator opens a business.
2. They inspect its current status.
3. If an authorized status action exists, they select it.
4. The portal explains the consequence of the action.
5. The administrator confirms.
6. Positive flow: the status changes and the updated state is displayed.
7. Cancelled action: no change is made.
8. Invalid transition: explain that the requested status change is not permitted.
9. Related restrictions: communicate the effect on outlets, users, and access only when those effects are defined and confirmed by the backend.
10. Request fails: retain the previous status and show an error unless the result is uncertain, in which case reload the authoritative status.

Business suspension and business reactivation should not be assumed to be implemented merely because account suspension and reactivation exist. They are separate lifecycle capabilities unless explicitly connected by the product rules.

## 5. Outlets section

Purpose: Manage individual restaurant locations belonging to a business. An outlet has its own identity and may have its own menu, tables, configuration, and operational limits.

### 5.1 Outlet directory and viewing

1. The administrator opens Outlets, or opens a business and selects one of its outlets.
2. The portal loads the relevant outlets.
3. The administrator selects an outlet.
4. The outlet detail view displays its core information, parent business, status, and supported configuration.
5. Positive flow: the outlet opens and its available details are displayed.
6. No outlets: show an empty state and an available creation path.
7. No matching results: show a no-results state.
8. Outlet belongs to another business: display its correct parent business and avoid associating it with the wrong tenant.
9. Outlet not found or inaccessible: show an appropriate error and return the administrator to a valid page.
10. Partial details fail to load: keep the available information usable while clearly marking the failed section.

### 5.2 Add an outlet

1. The administrator starts Add Outlet from the outlet directory or a business detail view.
2. The portal asks which business owns the outlet, unless that business is already selected.
3. The administrator enters the required outlet information.
4. They submit the form.
5. Positive flow: the outlet is created under the correct business and appears in the outlet directory and parent business details.
6. Parent business missing or unavailable: prevent creation and ask the administrator to select a valid business.
7. Duplicate identifier or slug: explain the conflict and ask for a valid alternative, where appropriate.
8. Invalid input: highlight the relevant issue and preserve entered values.
9. Business status prevents creation: explain the restriction if the product rules prohibit adding outlets to that business.
10. Request fails: keep the form available for correction or retry.
11. Repeated submission: prevent accidental duplicate outlets.

### 5.3 Edit an outlet

1. The administrator opens the outlet.
2. They choose Edit.
3. The current values appear.
4. They update the permitted information and submit.
5. Positive flow: save and display the updated outlet.
6. Validation or uniqueness error: identify the problem and preserve the changes.
7. Conflicting concurrent edit: reload and reconcile the latest state.
8. Save failure: retain the unsaved values.
9. Change affects public identification: show the resulting identifier or public URL when that is part of the supported workflow, and make the impact clear before confirmation.

### 5.4 Outlet Detail sections

The final outlet detail experience should provide access to relevant operational and administrative information, depending on backend support:

- Core outlet information and its parent business.
- Outlet status.
- Associated memberships or users.
- Subscription information or entitlements relevant to the outlet, if exposed.
- Branding and public-menu configuration, if platform administrators are allowed to manage it.
- Subscription history, when implemented.
- Available administrative actions.

For each detail section:

1. Open the section.
2. Load the relevant data.
3. Display the data or a clear empty state.
4. If loading fails, show a section-level error and retry path.
5. If an action changes the underlying record, refresh the affected detail section.
6. If the section is not available to the current administrator, deny access instead of displaying misleading placeholder data.

## 6. Users and access management

Purpose: Inspect user accounts and manage their platform-level access and relationships to businesses or outlets. A restaurant user's access should not be confused with a platform administrator's authority.

### 6.1 User directory

1. The administrator opens Users.
2. The portal loads the users the administrator is allowed to inspect.
3. The administrator searches, filters or opens a user.
4. The user detail view shows the supported account information, account status, roles, and relevant business/outlet relationships.
5. Positive flow: the selected user opens successfully.
6. No users: show an empty state.
7. No search matches: show a no-results state.
8. User no longer exists or is inaccessible: show a not-found or access-denied state.
9. Related business or outlet fails to load: distinguish the missing relationship details from the user's own account information.

### 6.2 User detail and role visibility

1. The administrator opens a user.
2. The portal displays the roles and relationships currently recorded by the backend.
3. The administrator inspects the user's access.
4. They navigate to a related business, outlet, or relevant audit event when links are available.
5. Positive flow: the relationships and roles are displayed accurately.
6. No memberships: show that no business/outlet relationship exists.
7. No platform role: display that the user has no platform-admin role.
8. Role or membership changed elsewhere: refresh the current state before making another change.
9. Permission boundary: a business-level role must not automatically grant platform-wide administrative permissions.

### 6.3 Operator management

This is an intended portal capability for managing authorized platform operators. The exact set of role-management operations must match the backend's supported permissions.

1. The administrator opens the operator-management section.
2. The portal lists the platform operators and their current roles/status.
3. The administrator opens an operator's details.
4. If authorized, they choose a supported action to change the operator's access.
5. The portal explains the consequences and requests confirmation for sensitive changes.
6. Positive flow: the change succeeds and the updated role/status is displayed.
7. Unauthorized change: the backend rejects the action and the UI reports the denial.
8. Attempt to remove or demote the last required Owner: prevent the operation if it would violate the platform's Owner invariants.
9. Attempt to modify one's own privileged access: enforce the backend's self-modification safeguards.
10. Concurrent change: refresh the operator's current role before retrying.
11. Change succeeds but access is reduced: subsequent requests must reflect the new permissions, even if the old session is still open.
12. Failure: preserve the current role/status and provide a safe retry path.

### 6.4 Platform Owner transfer

Owner transfer is a high-risk administrative workflow and should be treated separately from ordinary operator management.

1. The administrator opens the platform Owner-management area.
2. The current Owner information and eligible transfer options are shown, subject to the user's permissions.
3. The administrator selects the intended new Owner.
4. The portal clearly explains that this is a privileged role transfer.
5. The administrator reviews and confirms the operation.
6. Positive flow: the backend completes the transfer atomically; the new Owner is shown as the Owner and the former Owner's role reflects the resulting permissions.
7. Cancelled transfer: no role change occurs.
8. Invalid target: reject an ineligible or nonexistent target.
9. Concurrent transfers: if another transfer occurs at the same time, only a valid transaction may succeed; the portal reloads the final authoritative Owner state.
10. Last-Owner invariant: never leave the platform without a valid active Owner due to a partial update.
11. Transfer fails: show that the transfer did not complete, or reload and verify if the outcome is uncertain.
12. Old Owner still has the page open: their next protected request must be evaluated against the new permissions.

### 6.5 Suspend a user account

This is the account-level suspension workflow, distinct from suspending a business.

1. The administrator opens the user details.
2. They select Suspend Account, if authorized.
3. The portal explains that the account's access will be restricted according to the platform's suspension rules.
4. The administrator confirms.
5. Positive flow: the account is suspended, the displayed status updates, and an audit record is created.
6. Cancelled action: the account remains unchanged.
7. Already suspended: show the current state and avoid repeating an unnecessary operation.
8. Protected account: reject suspension when the target violates Owner/self-protection rules.
9. Concurrent action: if another administrator has already changed the account, refresh and report the current state.
10. Request fails: do not claim the account was suspended.
11. Uncertain outcome: reload the account status and audit trail before retrying.
12. Suspended user has an active session: subsequent backend requests must enforce suspension rather than trusting an old token alone.

### 6.6 Reactivate a user account

1. The administrator opens a suspended user.
2. They select Reactivate Account, if authorized.
3. The portal explains that account access may become available again.
4. The administrator confirms.
5. Positive flow: the account becomes active and the displayed status updates; the action is audited.
6. Already active: display the current state and avoid a duplicate change.
7. Account no longer eligible for reactivation: show the reason if available.
8. Permission error or backend failure: leave the result unclaimed and reload the authoritative status.
9. Uncertain outcome: inspect the current status before retrying.
10. Account is active again: normal authorization rules still apply; reactivation must not automatically grant privileged roles that the user no longer has.

## 7. Plans and feature/limit management

Purpose: Define the plans ROMS offers and the features or usage limits associated with each plan.

This is the configuration side of subscriptions: it answers what a customer plan permits. It is different from inspecting the subscription of an individual business.

### 7.1 Plan Catalog

1. The administrator opens Plan Catalog.
2. The portal loads the available plans.
3. Each plan shows its available identifying information and supported status.
4. The administrator opens a plan to inspect its details.
5. Positive flow: plans load and the administrator can inspect a selected plan.
6. No plans: show an empty state if the catalog is not configured yet.
7. Loading failure: show an error and retry option.
8. Plan no longer exists: return to the catalog with a clear message.

### 7.2 Create a plan

1. The administrator selects Add Plan.
2. The plan-entry form opens.
3. The administrator enters the plan's permitted information.
4. They submit the form.
5. Positive flow: the plan is created and appears in the catalog.
6. Missing required information: show validation errors and preserve the form.
7. Duplicate plan identifier: explain the conflict.
8. Unsupported feature or limit: reject the invalid configuration rather than silently ignoring it.
9. Request fails: preserve the entered values and allow retry.
10. Repeated submission: prevent accidental duplicate plans.

### 7.3 Edit a plan

1. The administrator opens a plan.
2. They select Edit.
3. The existing plan configuration appears.
4. They change permitted information, features or limits.
5. They submit and review the outcome.
6. Positive flow: the saved configuration is displayed.
7. Validation failure: explain which configuration is invalid.
8. Concurrent edit: reload the latest configuration before retrying.
9. Save failure: retain the unsaved edits.
10. Plan is already used by subscriptions: make the impact of changes clear before confirmation, according to the defined subscription rules.
11. Existing customer entitlements: do not silently assume that every plan change should immediately alter existing customers' access. The product must define whether changes apply immediately, on renewal, or only to future subscriptions.

### 7.4 Features and limits mapping

1. The administrator opens the feature/limit mapping for a plan.
2. The portal shows the supported capabilities and their current settings.
3. The administrator changes an allowed feature or limit.
4. They review and save the configuration.
5. Positive flow: the new configuration is saved and shown.
6. Invalid limit: explain the allowed values or reject the invalid configuration.
7. Unknown feature: do not save an unsupported feature key.
8. Save failure: preserve the unsaved settings.
9. Existing subscriptions affected: communicate the consequences if they are known.
10. Backend enforcement: changing a plan setting must not be treated as successful enforcement until the backend's entitlement checks actually apply the setting.

### 7.5 Retire or deactivate a plan

If plan deactivation is supported:

1. The administrator opens the plan.
2. They choose the supported deactivation action.
3. The portal explains the consequences for new subscriptions and existing subscribers.
4. The administrator confirms.
5. Positive flow: the plan's availability is updated.
6. Plan still in use: apply the defined policy; do not accidentally delete customer subscription history.
7. Cancellation: no change occurs.
8. Failure: preserve the prior state and verify the result before retrying.

## 8. Subscriptions and customer entitlement visibility

Purpose: Let platform administrators understand the subscription state of a business or outlet and troubleshoot plan-related issues.

Plan Catalog defines the available offerings; Subscription Management shows what is associated with a particular customer.

### 8.1 View subscription information

1. The administrator opens a business or outlet.
2. They open its subscription information.
3. The portal loads the subscription details exposed to the administrator.
4. The administrator can inspect the current subscription status, plan association and supported entitlement summary.
5. Positive flow: the details load.
6. No subscription record: display that no subscription is associated, if this is a valid state.
7. Plan cannot be resolved: indicate that the associated plan information is unavailable or inconsistent.
8. Subscription data unavailable: show a clear error rather than interpreting the missing data as an inactive subscription.
9. Multiple relevant records: show the correct relationship and status rather than arbitrarily displaying one.
10. Stale data: refresh before using the information to make a consequential decision.

### 8.2 Subscription history

1. The administrator opens the subscription history section for an outlet.
2. The portal retrieves the available historical records.
3. The administrator reviews the sequence of recorded subscription changes.
4. Positive flow: history appears in its correct chronological order, with clear status changes and available timestamps.
5. No history: show an empty state.
6. Older records unavailable: indicate the limitation rather than implying the visible history is complete.
7. History fails to load: show an error and retry option.
8. Open a history entry: display its available details without implying that viewing it changes the subscription.

### 8.3 Subscription changes

The UI should support changing a subscription only if the backend provides the required, authorized operations. Viewing subscription information does not imply permission to edit it.

For any supported change:

1. Open the subscription.
2. Select an available action.
3. Review the current state and proposed change.
4. Confirm the change.
5. Positive flow: show the saved state and refresh the relevant business/outlet details.
6. Invalid transition: explain why the change is not allowed.
7. Concurrent update: reload the current subscription before retrying.
8. Failure: do not display the intended status as if it were saved.
9. Uncertain outcome: query the current subscription state before repeating the action.
10. Entitlement impact: communicate known consequences for plan features and limits; do not assume payment processing or billing operations exist unless separately implemented.

## 9. Audit Logs and administrative activity

Purpose: Provide traceability for important administrative actions. This is especially important for role changes, Owner transfers, account suspension/reactivation, business provisioning and other sensitive operations.

### 9.1 Audit log directory

1. The administrator opens Audit Logs.
2. The portal loads the audit records available to that administrator.
3. The administrator reviews the records and applies supported filters or searches.
4. They open a record for more detail.
5. Positive flow: the record list loads and relevant details can be inspected.
6. No audit records: show an empty state.
7. No filter matches: show a no-results state.
8. Data load failure: show an error and retry option.
9. Large history: paginate or load records in manageable sections.
10. Older history unavailable: make the scope of the visible records clear if the system does not provide the full history.

### 9.2 Audit record detail

1. The administrator opens an audit entry.
2. The portal displays the information recorded for the action, such as the action type, target, timestamp, outcome and available actor/incident context.
3. If a related user, business or outlet can be reliably identified, the administrator can navigate to it.
4. Positive flow: the record's available details are displayed accurately.
5. Target no longer exists: retain the audit entry and identify the target as unavailable or deleted, rather than hiding the historical action.
6. Actor identity incomplete: show the available attribution and its limitations.
7. Record missing or inaccessible: show an appropriate error.
8. Read-only behavior: opening an audit record must not modify the underlying action or its history.

### 9.3 Verify a sensitive action

1. The administrator completes a sensitive operation, such as transferring Owner or suspending a user.
2. The operation returns its outcome.
3. The administrator opens Audit Logs.
4. They locate the relevant record.
5. Positive flow: the record reflects the action and its recorded outcome.
6. Audit record is not immediately visible: refresh or recheck according to the system's consistency behavior.
7. Action succeeded but the audit record is missing: treat this as an operational issue requiring investigation, not as proof that the action failed.
8. Action failed: the UI must not fabricate a successful audit result.

Audit logs should be treated as historical evidence, not as a substitute for checking the current state of a user, business, outlet or subscription.

## 10. Support and troubleshooting workflows

These are useful future capabilities, but they should be treated as optional until the product scope and backend authorization rules are decided.

### 10.1 Investigate a customer issue

1. The administrator receives a support issue.
2. They search for the relevant business, outlet or user.
3. They open the relevant details.
4. They inspect status, roles, subscription information and available audit records.
5. They identify the relevant state or error.
6. Positive flow: the available information helps them understand the issue.
7. No matching customer: show no results and allow another search.
8. Insufficient permissions: explain that the relevant information is not accessible.
9. Insufficient evidence: show what is known without inventing a cause.
10. Issue requires a privileged action: navigate to the appropriate authorized workflow instead of silently changing data from a support view.

### 10.2 Credential or account recovery tools

If administrative account recovery tools are added later:

1. The administrator opens the relevant account.
2. They choose an approved recovery action.
3. The portal explains the effect and any required verification.
4. They confirm the action.
5. Positive flow: show the confirmed result and create the appropriate audit record.
6. Invalid target or insufficient authorization: reject the action.
7. Recovery action fails: show failure without exposing secrets.
8. Sensitive output: do not expose passwords, credentials or reusable secrets in page content, URLs, logs or audit details.

Do not assume a direct password-reset tool or a temporary login/impersonation feature is part of the current implementation. Those need separate product and security decisions.

## 11. Cross-cutting flows that every section must handle

These aren't necessarily separate pages. They are behaviors that should work consistently throughout the portal.

### 11.1 Search, filtering and pagination

1. Open a directory.
2. Enter a search term or select a filter.
3. The results update to match the criteria.
4. Move to another page of results.
5. Open a record.
6. Return to the directory.
7. Positive flow: the results reflect the selected criteria.
8. No results: display a helpful empty state with an option to clear filters.
9. Search request fails: show an error without pretending that there are no matching records.
10. Filters conflict: allow the administrator to clear or modify them.
11. Record changes between pages: refresh the affected results when appropriate.
12. Search input changes rapidly: avoid showing an older response as though it matches the latest search.

### 11.2 Form validation and unsaved changes

1. Open a form.
2. Enter information.
3. Submit.
4. Valid input: continue to the save operation.
5. Invalid input: identify the problem and preserve the user's entries.
6. Leave with unsaved changes: warn the administrator before discarding changes.
7. Cancel editing: return to the previous view without saving.
8. Backend rejects otherwise valid-looking input: display the server's validation result in understandable language.
9. Duplicate submission: avoid repeating the same create or update operation unnecessarily.
10. Save succeeds: show the saved values, not merely the values the administrator attempted to submit.

### 11.3 Destructive or privileged actions

Examples include Owner transfer, account suspension, operator-role changes and plan deactivation.

1. The administrator initiates the action.
2. The portal explains the consequence.
3. The administrator reviews the target and confirms.
4. The backend checks permissions and whether the operation is valid.
5. Positive flow: the operation succeeds and the affected state is refreshed.
6. Cancel: no change occurs.
7. Target changes before confirmation: revalidate the operation against the current state.
8. Permission revoked: deny the operation.
9. Conflict or invalid state: explain the failure and show the current state.
10. Timeout or uncertain result: verify the result before offering a repeat action.
11. Audit: record the action and outcome according to the platform's audit policy.

### 11.4 Loading, empty, error and success states

Every data-backed section should have a defined response for:

- Loading: data is being retrieved or a change is processing.
- Success: data loaded or the requested operation completed.
- Empty: the request succeeded but there is no data to display.
- Validation error: the submitted information needs correction.
- Permission error: the administrator cannot perform or view the requested operation.
- Not found: the requested record does not exist or is no longer available.
- Conflict: the operation conflicts with current state or another change.
- Network/server error: the request could not be completed.
- Unknown outcome: the request may have succeeded, so the current state must be checked before retrying.

A particularly important distinction: an empty result is not the same as a failed request. A failed subscription lookup, for example, must not be interpreted as proof that a business has no subscription.

## 12. End-to-end journey examples

These journeys combine multiple sections into realistic administrative tasks.

### Journey A — Onboard a new restaurant business

1. Sign in as an authorized Platform Admin.
2. Open Businesses and choose Add Business.
3. Enter the required business information and submit.
4. Review the new business details.
5. Open Outlets and create the first outlet under that business.
6. Open the outlet and verify that its parent business is correct.
7. Inspect the available plan/subscription information and other supported setup details.
8. Confirm the new records are visible in the relevant directories.

Failure branches: invalid business data → correct and retry; duplicate identifier → resolve the conflict; outlet creation fails → retain the business and retry outlet creation; uncertain create result → verify existing records before retrying.

### Journey B — Investigate a restaurant access issue

1. Open Users and locate the affected user.
2. Inspect the user's account status and permissions.
3. Open the related business or outlet.
4. Inspect the available subscription and entitlement information.
5. Review the relevant audit records.
6. Determine whether the issue relates to account status, permissions, subscription state or missing information.
7. Perform an authorized corrective action if the necessary workflow exists.
8. Verify the current state and inspect the recorded outcome.

Failure branches: no matching user → check the search criteria; incomplete audit evidence → investigate without guessing; action denied → respect the permission boundary; timeout → verify state before retrying.

### Journey C — Suspend an account and later restore it

1. Open the target user's details and verify the identity.
2. Choose Suspend Account and review the consequences.
3. Confirm the action.
4. Verify that the account status changed and the audit record exists.
5. Later, return to the same account and verify its current state.
6. Choose Reactivate Account and confirm.
7. Verify the new status and audit record.

Failure branches: protected Owner/self target → reject; already suspended/active → show current state; request fails → do not claim success; uncertain outcome → reload before repeating.

### Journey D — Transfer platform ownership

1. Open the Owner-management area.
2. Review the current Owner and select an eligible replacement.
3. Review the high-impact confirmation.
4. Confirm the transfer.
5. Verify that the new Owner is recorded and the previous Owner has the correct resulting role.
6. Review the audit record.

Failure branches: invalid replacement → reject; concurrent transfer → reload the final state; partial failure → investigate the authoritative role state; missing audit record → flag for investigation.

### Journey E — Update a plan

1. Open Plan Catalog and select the intended plan.
2. Review its current configuration.
3. Edit the supported features or limits.
4. Review any known impact on existing subscriptions.
5. Save the changes.
6. Reopen or refresh the plan and verify the saved configuration.

Failure branches: invalid mapping → correct it; concurrent edit → reload; existing subscriptions affected → follow the defined policy; save failure → preserve edits and retry safely.

## 13. What the final portal is expected to cover

Use this checklist while designing the pages and their interactions.

### Portal design checklist

0 / 33 covered

Access and overview

Platform Admin sign-in and session handling

Authorization and access-denied states

Platform overview dashboard

Recent administrative activity

Business operations

Business directory, search and filters

Add and edit business

Business details and status

Outlet directory and search

Add and edit outlet

Outlet details and related information

Users and governance

User directory and user details

Role and membership visibility

Operator management

Platform Owner transfer

Account suspension

Account reactivation

Plans and subscriptions

Plan Catalog

Create and edit plans

Feature and limit mappings

Plan deactivation, if supported

Subscription summary

Subscription history

Supported subscription changes

Audit and troubleshooting

Audit log directory and filters

Audit record detail

Verification of sensitive actions

Support investigation workflow, if approved

Shared behaviors

Loading, empty and error states

Validation and unsaved changes

Confirmation and cancellation

Duplicate submissions and retries

Concurrent changes and stale data

Permission failures and not-found states

Reset checklistCopy checklist

## 14. Important decisions to keep separate from UI design

You can design the page flows now without deciding every backend detail. However, these decisions affect what actions the final portal should expose.

| Decision                                | Why it matters                                                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Business suspension vs. user suspension | These affect different entities and may have different consequences.                                              |
| Owner transfer safeguards               | Determines which transfers are permitted and how the portal explains the impact.                                  |
| Operator role-management permissions    | Determines which administrators can grant, remove or change privileged access.                                    |
| Subscription visibility                 | Determines whether subscription details are visible only to platform administrators or also to restaurant owners. |
| Plan changes for existing customers     | Determines whether entitlements change immediately, at renewal, or only for new subscriptions.                    |
| Business/outlet status rules            | Determines which actions are allowed when a business or outlet is inactive or suspended.                          |
| Support and recovery tools              | Password recovery, temporary access and impersonation carry additional security risks and need explicit approval. |
| Audit retention and completeness        | Determines which historical actions can be inspected and for how long.                                            |

The first three decisions that particularly affect the portal's workflows are the Owner transfer process, operator management, and account suspension/reactivation. Subscription visibility and plan-change behavior also need product decisions before their flows can be finalized.

One final distinction for your UI work: a page or action described here is part of the target product experience, not a claim that its backend operation already exists. While designing, you can show the full intended flow, then later map each action to the implemented backend capability and identify any missing pieces.