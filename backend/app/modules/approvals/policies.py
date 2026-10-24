"""Approval authorization policies and eligibility checkers.

Enforces three-tier ROMS platform role permissions (Owner, Admin, Operator):
- Request creation eligibility
- Approver eligibility per request type and target role
- Self-approval constraints based on target's current role
- Role transition authority (Admin promotion of an existing Operator is permitted for Admins;
  modifying, suspending, or demoting an existing Admin strictly requires Owner authority;
  Owner is fully protected from Admin actions)
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.modules.staff.models import User
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.core.errors import ForbiddenError, ValidationError, NotFoundError

VALID_PLATFORM_ROLES = {"owner", "admin", "operator"}


def get_effective_platform_role(user: User) -> Optional[str]:
    """
    Resolves the effective platform role of a user following the transitional model:
    - If user.status != 'active', returns None.
    - If platform_role is 'owner' or 'admin', requires is_platform_admin == True.
    - If platform_role is 'operator', requires is_platform_admin == False.
    - If platform_role is None and is_platform_admin is True, treats as 'admin' (legacy bridge).
    - Contradictory pairs or inactive users return None.
    """
    if not user or user.status != "active":
        return None

    role = user.platform_role
    if role is not None:
        if role not in VALID_PLATFORM_ROLES:
            return None
        if role in ("owner", "admin") and not user.is_platform_admin:
            return None
        if role == "operator" and user.is_platform_admin:
            return None
        return role

    if user.is_platform_admin:
        return "admin"

    return None


def check_can_create_request(actor: User, request_type: str, payload: dict) -> None:
    """
    Validates whether the actor is authorized to submit an approval request of this type.
    - Owner and Admin can submit any valid request type.
    - Operators can submit ordinary operational requests (e.g., outlet creation, routine subscription changes).
    - Operators CANNOT request user suspension or reactivation.
    - Users CANNOT initiate self-suspension.
    """
    role = get_effective_platform_role(actor)
    if not role:
        raise ForbiddenError("Active platform credentials are required to submit approval requests.")

    if request_type == "user_reactivation" and role != "owner":
        raise ForbiddenError("User reactivation requests are strictly Platform Owner controlled.")

    if request_type == "user_suspension":
        target_uid_val = payload.get("target_user_id") or payload.get("user_id")
        if target_uid_val and str(target_uid_val) == str(actor.id):
            raise ForbiddenError("Users cannot initiate self-suspension.")


def check_approver_eligibility(
    db: Session,
    approver: User,
    request: ApprovalRequest,
) -> None:
    """
    Validates that the approver is authorized to decide the approval request.
    Enforces target-role revalidation, self-approval policies, and role boundaries:
    - Approver must be an active Platform Administrator or the Platform Owner.
    - Owner-targeted actions (role change, suspension, revocation) can NEVER be approved by an Admin.
    - Admin-targeted actions (suspension, demotion, revocation) strictly require Platform Owner approval.
    - Promoting an existing Operator to Admin is permitted for Admin approval and self-approval.
    - Self-approval by an Admin is restricted to Operator-targeted actions and permitted tenant actions.
    """
    role = get_effective_platform_role(approver)
    if not role or role not in ("owner", "admin"):
        raise ForbiddenError("Only active Platform Administrators or the Platform Owner may decide approval requests.")

    # Resolve target user from authoritative persisted database state
    payload = request.payload_snapshot or {}
    target_uid_val = payload.get("target_user_id") or payload.get("user_id")
    target_user = None
    if target_uid_val:
        try:
            target_uuid = uuid.UUID(str(target_uid_val))
            target_user = db.query(User).filter(User.id == target_uuid).first()
        except (ValueError, TypeError):
            pass

    target_role = get_effective_platform_role(target_user) if target_user else None
    target_is_owner = bool(target_user and (target_user.platform_role == "owner" or target_role == "owner"))
    target_is_admin = bool(target_user and (target_user.is_platform_admin or target_role in ("admin", "owner"))) and not target_is_owner

    # 1. Platform Owner protections (Decision-time guard):
    # Platform Administrators can NEVER approve role changes, suspension, or revocation of the Platform Owner
    if target_is_owner and role != "owner":
        if request.request_type == "user_role_change":
            raise ForbiddenError("Role changes targeting the Platform Owner require Platform Owner authority.")
        if request.request_type == "user_suspension":
            raise ForbiddenError("Only the Platform Owner can suspend another Platform Administrator.")
        if request.request_type == "operator_revocation":
            raise ForbiddenError("Platform Administrators cannot alter privileges of the Platform Owner.")

    # 2. Platform Administrator protections:
    # Suspension, demotion, or revocation of an existing Admin requires Platform Owner authority
    if target_is_admin and role != "owner":
        if request.request_type == "user_suspension":
            raise ForbiddenError("Only the Platform Owner can suspend another Platform Administrator.")
        if request.request_type == "user_role_change":
            raise ForbiddenError("Role changes involving Platform Administrator privileges require Platform Owner final approval.")
        if request.request_type == "operator_revocation":
            raise ForbiddenError("Platform Administrators cannot revoke administrator privileges.")

    # 3. Role change governance:
    if request.request_type == "user_role_change":
        target_new_role = payload.get("new_platform_role")
        if target_new_role == "owner":
            raise ForbiddenError("Platform Owner role can only be transferred via the dedicated owner transfer process.")
        # Promoting an existing Operator to Admin is permitted for Admins.
        # However, promoting a non-operator or unknown target to Admin requires Platform Owner.
        if target_new_role == "admin" and target_role != "operator" and role != "owner":
            raise ForbiddenError("Promoting a non-operator to Platform Administrator requires Platform Owner final approval.")

    # 4. Owner-only request types
    owner_only_types = {
        "user_reactivation",
        "entitlement_override",
    }
    if request.request_type in owner_only_types and role != "owner":
        raise ForbiddenError(f"Decision for '{request.request_type}' requires Platform Owner authority.")

    # 5. Self-approval constraints
    is_self_action = (approver.id == request.requester_user_id)
    if is_self_action:
        # Platform Owner may self-approve any authorized request
        if role == "owner":
            return

        # Confirmed Platform Admin Self-Approval Rules:
        # An Admin may self-approve only actions involving a target who is currently an Operator:
        # 1. Create/provision an Operator (operator_creation)
        # 2. Promote an existing Operator to Admin (user_role_change where target is currently an Operator)
        # 3. Suspend an Operator (user_suspension where target is currently an Operator)
        # 4. Revoke an Operator (operator_revocation where target is currently an Operator)
        # Plus permitted tenant operations: business_creation, subscription_change
        is_self_approval_permitted = False

        if request.request_type in ("business_creation", "subscription_change"):
            is_self_approval_permitted = True
        elif request.request_type == "operator_creation":
            # If target_user_id is supplied, target must not already be an Admin or Owner
            if target_user and (target_user.is_platform_admin or target_role in ("admin", "owner")):
                is_self_approval_permitted = False
            else:
                is_self_approval_permitted = True
        elif request.request_type == "user_role_change":
            target_new_role = payload.get("new_platform_role")
            if target_role == "operator" and target_new_role == "admin":
                is_self_approval_permitted = True
        elif request.request_type == "user_suspension":
            if target_role == "operator":
                is_self_approval_permitted = True
        elif request.request_type == "operator_revocation":
            if target_role == "operator":
                is_self_approval_permitted = True

        if not is_self_approval_permitted:
            raise ForbiddenError(
                f"Platform Administrators cannot self-approve '{request.request_type}' requests. A separate approver is required."
            )

