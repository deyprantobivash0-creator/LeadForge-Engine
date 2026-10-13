"""Structural action authority, separate from identity and contextual policy."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType


class ActionPermission(StrEnum):
    LEAD_READ = "lead.read"
    LEAD_CREATE = "lead.create"
    LEAD_LIFECYCLE_CHANGE = "lead.lifecycle.change"
    LEAD_PROCESS = "lead.process"
    LEAD_IMPORT = "lead.import"
    ANALYSIS_READ = "analysis.read"
    REPORT_READ = "report.read"
    WORKSPACE_READ = "workspace.read"


# Explicit current actions; adding an enum member must not automatically grant it.
CURRENT_MEMBER_PERMISSIONS = frozenset({
    ActionPermission.LEAD_READ, ActionPermission.LEAD_CREATE,
    ActionPermission.LEAD_LIFECYCLE_CHANGE, ActionPermission.LEAD_PROCESS,
    ActionPermission.LEAD_IMPORT, ActionPermission.ANALYSIS_READ,
    ActionPermission.REPORT_READ, ActionPermission.WORKSPACE_READ,
})
ROLE_PERMISSIONS = MappingProxyType({
    "owner": CURRENT_MEMBER_PERMISSIONS,
    "admin": CURRENT_MEMBER_PERMISSIONS,
    "member": CURRENT_MEMBER_PERMISSIONS,
})


def _validate_context(principal, capabilities):
    if not isinstance(principal, ExecutionPrincipal):
        raise ValueError("A typed execution principal is required.")
    ExecutionPrincipal.model_validate(principal)
    if type(capabilities) is not frozenset or any(type(p) is not ActionPermission for p in capabilities):
        raise ValueError("Capabilities must be immutable typed action permissions.")


@dataclass(frozen=True)
class HumanAuthorizationContext:
    """Trusted live-membership snapshot; capabilities may only narrow a role."""
    principal: ExecutionPrincipal
    role: str
    capabilities: frozenset[ActionPermission]

    def __post_init__(self):
        _validate_context(self.principal, self.capabilities)
        if self.principal.principal_type != PrincipalType.USER or type(self.role) is not str:
            raise ValueError("Human authority requires USER identity and membership role.")


@dataclass(frozen=True)
class MachineAuthorizationContext:
    """Trusted internal assignment, never a grant inferred from raw client JSON."""
    principal: ExecutionPrincipal
    capabilities: frozenset[ActionPermission]

    def __post_init__(self):
        _validate_context(self.principal, self.capabilities)
        if self.principal.principal_type == PrincipalType.USER:
            raise ValueError("Machine authority cannot impersonate USER authority.")

    def to_dict(self):
        # Transportable shape is not producer authentication. No from_dict ingress.
        return {"principal": self.principal.model_dump(mode="json"),
                "capabilities": sorted(p.value for p in self.capabilities)}


AuthorizationContext = HumanAuthorizationContext | MachineAuthorizationContext


def effective_permissions(context: AuthorizationContext) -> frozenset[ActionPermission]:
    if type(context) is HumanAuthorizationContext:
        return ROLE_PERMISSIONS.get(context.role, frozenset()) & context.capabilities
    if type(context) is MachineAuthorizationContext:
        return context.capabilities
    return frozenset()


def delegate_capabilities(parent: AuthorizationContext, child: ExecutionPrincipal,
                          capabilities: frozenset[ActionPermission]) -> MachineAuthorizationContext:
    """Trusted narrowing only; this does not authenticate or persist delegation."""
    if type(parent) not in {HumanAuthorizationContext, MachineAuthorizationContext}:
        raise ValueError("Trusted parent authority is required.")
    _validate_context(parent.principal, parent.capabilities)
    _validate_context(child, capabilities)
    expected_parent = ActorReference(principal_type=parent.principal.principal_type,
                                     actor_id=parent.principal.actor_id)
    if (child.organization_id != parent.principal.organization_id
            or child.correlation_id != parent.principal.correlation_id
            or child.delegated_by != expected_parent):
        raise ValueError("Delegation identity, tenant or correlation mismatch.")
    if not capabilities <= effective_permissions(parent):
        raise ValueError("Delegation cannot expand structural authority.")
    return MachineAuthorizationContext(child, capabilities)


class PermissionResult(StrEnum):
    PERMIT = "PERMIT"
    DENY = "DENY"


class PermissionReason(StrEnum):
    PERMITTED_BY_ROLE = "PERMITTED_BY_ROLE"
    PERMITTED_BY_CAPABILITY = "PERMITTED_BY_CAPABILITY"
    DENIED_PERMISSION_NOT_GRANTED = "DENIED_PERMISSION_NOT_GRANTED"
    DENIED_INVALID_CONTEXT = "DENIED_INVALID_CONTEXT"
    DENIED_TENANT_MISMATCH = "DENIED_TENANT_MISMATCH"
    DENIED_PRINCIPAL_MISMATCH = "DENIED_PRINCIPAL_MISMATCH"
    DENIED_UNKNOWN_ROLE = "DENIED_UNKNOWN_ROLE"
    DENIED_UNKNOWN_PERMISSION = "DENIED_UNKNOWN_PERMISSION"


@dataclass(frozen=True)
class PermissionDecision:
    result: PermissionResult
    permission: ActionPermission | None
    principal_type: PrincipalType | None
    reason_code: PermissionReason

    def to_dict(self):
        return {"result": self.result.value,
                "permission": self.permission.value if self.permission else None,
                "principal_type": self.principal_type.value if self.principal_type else None,
                "reason_code": self.reason_code.value}
