"""Explicit service identity checks and safe diagnostics, not permission policy."""

from backend.core.exceptions import LeadForgeException
from backend.core.logger import event
from backend.schemas.execution_principal import ExecutionPrincipal


def require_tenant_identity(principal: ExecutionPrincipal, organization_id: int) -> None:
    if not isinstance(principal, ExecutionPrincipal):
        raise LeadForgeException("Execution identity required.", status_code=400,
                                 error_code="EXECUTION_IDENTITY_REQUIRED")
    # Revalidate even an incorrectly constructed/copied internal model. Shape
    # validation still does not authenticate serialized data or grant authority.
    try:
        verified = ExecutionPrincipal.model_validate(principal.model_dump())
    except ValueError as exc:
        raise LeadForgeException("Invalid execution identity.", status_code=400,
                                 error_code="EXECUTION_IDENTITY_INVALID") from exc
    if type(organization_id) is not int or verified.organization_id != organization_id:
        raise LeadForgeException("Execution organization mismatch.", status_code=403,
                                 error_code="EXECUTION_TENANT_MISMATCH")


def execution_event(name: str, principal: ExecutionPrincipal) -> None:
    event(name, principal_type=principal.principal_type.value,
          organization_id=principal.organization_id, actor_id=principal.actor_id,
          correlation_id=principal.correlation_id)
