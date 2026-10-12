"""Browser adapter: authentication/CSRF/membership remain authoritative."""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.organization import require_authorized_csrf
from backend.database.dependencies import get_db
from backend.models.user import User
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.services.organization_authorization_service import (
    AuthorizedOrganizationContext, OrganizationAccessDenied, OrganizationAuthorizationService,
)


def principal_from_authorized_context(context: AuthorizedOrganizationContext, *,
                                      authenticated_user: User, db: Session,
                                      correlation_id: str) -> ExecutionPrincipal:
    # A dataclass label is not an authorization stamp. Check identity binding,
    # then resolve live membership with the existing authoritative service.
    if (not authenticated_user.is_active or context.user.id != authenticated_user.id
            or context.membership.user_id != authenticated_user.id
            or context.membership.organization_id != context.organization.id
            or not context.membership.is_active or not context.organization.is_active):
        raise OrganizationAccessDenied()
    verified = OrganizationAuthorizationService(db).authorize(authenticated_user, context.organization.id)
    return ExecutionPrincipal.for_user(authenticated_user.id, verified.organization.id,
                                       correlation_id=correlation_id)


def require_user_principal(
    request: Request,
    context: AuthorizedOrganizationContext = Depends(require_authorized_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExecutionPrincipal:
    return principal_from_authorized_context(context, authenticated_user=user, db=db,
                                              correlation_id=request.state.request_id)
