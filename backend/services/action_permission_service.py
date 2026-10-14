"""Service-boundary authority resolution; callers supply no trusted human role."""

from backend.core.exceptions import LeadForgeException
from backend.core.logger import event
from backend.repositories.permission_repository import PermissionRepository
from backend.schemas.action_permission import (
    ActionPermission, HumanAuthorizationContext, MachineAuthorizationContext,
    AuthorizationContext, PermissionDecision, PermissionResult, ROLE_PERMISSIONS,
)
from backend.schemas.execution_principal import PrincipalType
from backend.services.execution_identity import require_tenant_identity
from backend.services.permission_evaluator import evaluate_permission


class ActionPermissionService:
    def __init__(self, db):
        self.repository = PermissionRepository(db)

    def human_context(self, principal) -> HumanAuthorizationContext | None:
        if principal.principal_type != PrincipalType.USER:
            return None
        role = self.repository.active_role(principal.actor_id, principal.organization_id)
        if role is None:
            return None
        return HumanAuthorizationContext(principal, role, ROLE_PERMISSIONS.get(role, frozenset()))

    def require(self, principal, permission: ActionPermission, organization_id: int,
                machine_context: MachineAuthorizationContext | None = None):
        decision, _context = self.require_with_context(
            principal, permission, organization_id, machine_context)
        return decision

    def require_with_context(
        self, principal, permission: ActionPermission, organization_id: int,
        machine_context: MachineAuthorizationContext | None = None,
    ) -> tuple[PermissionDecision, AuthorizationContext | None]:
        """Return the actual gating decision and its same-time authority snapshot.

        Human authority is still resolved here from live membership. Returning
        the evaluated context avoids a second lookup/evaluation for audit.
        """
        require_tenant_identity(principal, organization_id)
        if principal.principal_type == PrincipalType.USER:
            # A supplied snapshot must never override current DB membership.
            context = self.human_context(principal) if machine_context is None else None
        else:
            context = machine_context
        decision = evaluate_permission(principal, context, permission, organization_id)
        event("permission.evaluated", principal_type=principal.principal_type.value,
              actor_id=principal.actor_id, organization_id=organization_id,
              correlation_id=principal.correlation_id, permission=decision.permission.value if decision.permission else None,
              permission_result=decision.result.value, reason=decision.reason_code.value)
        if decision.result != PermissionResult.PERMIT:
            raise LeadForgeException("Action not permitted.", status_code=403,
                                     error_code="ACTION_PERMISSION_DENIED")
        return decision, context
