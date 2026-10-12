from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.transactions import service_transaction
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.services.execution_identity import require_tenant_identity, execution_event

from backend.repositories.lead_repository import LeadRepository
from backend.schemas.lead_contract import LeadLifecycle


class LeadLifecycleService:

    ALLOWED_STATUSES = {item.value for item in LeadLifecycle}

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadRepository(db)

    def update_lifecycle_for_principal(
        self, principal: ExecutionPrincipal, *, lead_id: int, organization_id: int,
        status: str | None = None, notes: str | None = None,
        last_contacted: datetime | None = None, next_follow_up: datetime | None = None,
    ):
        with service_transaction(self.db):
            require_tenant_identity(principal, organization_id)
            execution_event("execution.lead.lifecycle", principal)
            return self.update_lifecycle(lead_id, organization_id, status, notes,
                                         last_contacted, next_follow_up)

    def update_status(
        self,
        lead_id: int,
        organization_id: int,
        status: str,
    ):

        with service_transaction(self.db):
            if status not in self.ALLOWED_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            return self.repository.update_status(
                lead_id=lead_id, organization_id=organization_id, status=status,
            )

    def update_lifecycle(
        self,
        lead_id: int,
        organization_id: int,
        status: str | None = None,
        notes: str | None = None,
        last_contacted: datetime | None = None,
        next_follow_up: datetime | None = None,
    ):

        with service_transaction(self.db):
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
