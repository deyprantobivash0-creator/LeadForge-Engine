"""Pure default-deny structural permission decisions. No IO, model or policy."""

from backend.schemas.action_permission import (
    ActionPermission, HumanAuthorizationContext, MachineAuthorizationContext,
    PermissionDecision, PermissionReason, PermissionResult, ROLE_PERMISSIONS, effective_permissions,
)
from backend.schemas.execution_principal import ExecutionPrincipal, PrincipalType


def evaluate_permission(principal, authorization_context, requested_permission,
                        target_organization_id) -> PermissionDecision:
    permission = requested_permission if type(requested_permission) is ActionPermission else None
    principal_type = None

    def deny(reason):
        return PermissionDecision(PermissionResult.DENY, permission, principal_type, reason)

    if permission is None:
        return deny(PermissionReason.DENIED_UNKNOWN_PERMISSION)
    if not isinstance(principal, ExecutionPrincipal):
        return deny(PermissionReason.DENIED_INVALID_CONTEXT)
    try:
        principal = ExecutionPrincipal.model_validate(principal)
    except ValueError:
        return deny(PermissionReason.DENIED_INVALID_CONTEXT)
    principal_type = principal.principal_type
    context = authorization_context
    if type(context) not in {HumanAuthorizationContext, MachineAuthorizationContext}:
        return deny(PermissionReason.DENIED_INVALID_CONTEXT)
    try:
        context.__post_init__()
    except (ValueError, TypeError):
        return deny(PermissionReason.DENIED_INVALID_CONTEXT)
    if (type(target_organization_id) is not int
            or principal.organization_id != target_organization_id
            or context.principal.organization_id != target_organization_id):
        return deny(PermissionReason.DENIED_TENANT_MISMATCH)
    if context.principal != principal:
        return deny(PermissionReason.DENIED_PRINCIPAL_MISMATCH)
    if principal_type == PrincipalType.USER:
        if type(context) is not HumanAuthorizationContext:
            return deny(PermissionReason.DENIED_INVALID_CONTEXT)
        if context.role not in ROLE_PERMISSIONS:
            return deny(PermissionReason.DENIED_UNKNOWN_ROLE)
        permitted_reason = PermissionReason.PERMITTED_BY_ROLE
    else:
        if type(context) is not MachineAuthorizationContext:
            return deny(PermissionReason.DENIED_INVALID_CONTEXT)
        permitted_reason = PermissionReason.PERMITTED_BY_CAPABILITY
    if permission not in effective_permissions(context):
        return deny(PermissionReason.DENIED_PERMISSION_NOT_GRANTED)
    return PermissionDecision(PermissionResult.PERMIT, permission, principal_type, permitted_reason)
