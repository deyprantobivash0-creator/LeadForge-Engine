from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.transactions import service_transaction
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.services.execution_identity import require_tenant_identity, execution_event
from backend.schemas.action_permission import ActionPermission, MachineAuthorizationContext
from backend.services.action_permission_service import ActionPermissionService

from backend.repositories.lead_repository import LeadRepository
from backend.schemas.lead_contract import LeadLifecycle


class LeadLifecycleService:

    ALLOWED_STATUSES = {item.value for item in LeadLifecycle}

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadRepository(db)

    def update_lifecycle(
        self, principal: ExecutionPrincipal, *, lead_id: int, organization_id: int,
        status: str | None = None, notes: str | None = None,
        last_contacted: datetime | None = None, next_follow_up: datetime | None = None,
        machine_context: MachineAuthorizationContext | None = None,
    ):
        with service_transaction(self.db):
            require_tenant_identity(principal, organization_id)
            ActionPermissionService(self.db).require(principal, ActionPermission.LEAD_LIFECYCLE_CHANGE,
                                                     organization_id, machine_context)
            execution_event("execution.lead.lifecycle", principal)
            return self._apply_lifecycle_change(lead_id, organization_id, status, notes,
                                                last_contacted, next_follow_up)

    def _apply_lifecycle_change(
        self,
        lead_id: int,
        organization_id: int,
        status: str | None = None,
        notes: str | None = None,
        last_contacted: datetime | None = None,
        next_follow_up: datetime | None = None,
    ):

        """Mutation detail for an authorized command; caller owns its transaction."""
        if status is not None and status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        return self.repository.update_lifecycle(
            lead_id=lead_id, organization_id=organization_id, status=status,
            notes=notes, last_contacted=last_contacted, next_follow_up=next_follow_up,
        )

    def get_follow_ups(
        self,
        organization_id: int,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
    ):
        return self.repository.get_follow_up_leads(
            organization_id=organization_id,
            days=days,
            page=page,
            page_size=page_size,
        )
