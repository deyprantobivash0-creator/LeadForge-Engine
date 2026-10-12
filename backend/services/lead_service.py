from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database.transactions import service_transaction
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.services.execution_identity import require_tenant_identity, execution_event

from backend.models.lead import Lead
from backend.repositories.lead_repository import LeadRepository


class LeadService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadRepository(db)

    def create_lead_for_principal(self, principal: ExecutionPrincipal, *, company: str,
                                  email: str, source: str, organization_id: int) -> Lead:
        with service_transaction(self.db):
            require_tenant_identity(principal, organization_id)
            execution_event("execution.lead.create", principal)
            return self.create_lead(company, email, source, organization_id)

    def create_lead(
        self,
        company: str,
        email: str,
        source: str,
        organization_id: int,
    ) -> Lead:

        try:
            with service_transaction(self.db):
                existing = self.repository.get_lead_by_email(
                    email=email, organization_id=organization_id,
                )
                if existing:
                    raise ValueError("A lead with this email already exists in this organization.")
                lead = Lead(company=company, email=email, source=source,
                            organization_id=organization_id)
                self.repository.create_lead(lead)
            return lead
        except IntegrityError as exc:
            # The advisory read can race. Classify only this exact uniqueness
            # constraint; the owning scope rolls back the entire operation.
            if self.repository.db.get_bind().dialect.name == "postgresql":
                diagnostic = getattr(exc.orig, "diag", None)
                duplicate = (
                    getattr(exc.orig, "sqlstate", None) == "23505"
                    and getattr(diagnostic, "constraint_name", None)
                    == "uq_leads_organization_email"
                )
            else:
                duplicate = (
                    getattr(exc.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
                    and str(exc.orig) == "UNIQUE constraint failed: leads.organization_id, leads.email"
                )
            if not duplicate:
                raise
            raise ValueError(
                "A lead with this email already exists in this organization."
            ) from exc

    def get_leads(
        self,
        organization_id: int,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        priority: str | None = None,
        processing_status: str | None = None,
        source: str | None = None,
        analysis_state: str | None = None,
    ):
        return self.repository.get_all_leads(
            organization_id=organization_id,
            page=page,
            page_size=page_size,
            status=status,
            priority=priority,
            processing_status=processing_status,
            source=source,
            analysis_state=analysis_state,
        )

    def get_lead(
        self,
        lead_id: int,
        organization_id: int,
    ):
        return self.repository.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

    def search_leads(
        self,
        organization_id: int,
        company: str | None = None,
        email: str | None = None,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        priority: str | None = None,
        processing_status: str | None = None,
        source: str | None = None,
        analysis_state: str | None = None,
    ):
        return self.repository.search_leads(
            organization_id=organization_id,
            company=company,
            email=email,
            page=page,
            page_size=page_size,
            status=status,
            priority=priority,
            processing_status=processing_status,
            source=source,
            analysis_state=analysis_state,
        )

    def get_follow_up_leads(
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
