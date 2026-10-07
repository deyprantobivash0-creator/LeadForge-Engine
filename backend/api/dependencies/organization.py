"""Authorized tenant context for customer routes."""

import re

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import get_current_user, require_csrf
from backend.core.exceptions import LeadForgeException
from backend.database.dependencies import get_db
from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.services.organization_authorization_service import (
    AuthorizedOrganizationContext,
    OrganizationAuthorizationService,
)


def get_current_organization(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthorizedOrganizationContext:
    values = request.headers.getlist("X-Organization-ID")
    if len(values) != 1 or re.fullmatch(r"[1-9][0-9]{0,18}", values[0]) is None:
        raise LeadForgeException("A valid X-Organization-ID header is required.", status_code=400, error_code="ORGANIZATION_SELECTOR_INVALID")
    organization_id = int(values[0])
    if organization_id > 9223372036854775807:
        raise LeadForgeException("A valid X-Organization-ID header is required.", status_code=400, error_code="ORGANIZATION_SELECTOR_INVALID")
    return OrganizationAuthorizationService(db).authorize(user, organization_id)


def require_authorized_csrf(
    context: AuthorizedOrganizationContext = Depends(get_current_organization),
    _session: AuthSession = Depends(require_csrf),
) -> AuthorizedOrganizationContext:
    return context
