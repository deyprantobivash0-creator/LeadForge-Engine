"""Canonical synchronous Lead Brain operation and its transaction boundaries."""

import logging
from time import monotonic
from backend.core.logger import event
from backend.core.config import settings

from sqlalchemy.orm import Session

from backend.database.transactions import in_service_transaction, service_transaction

from backend.ai.providers.base import (
    ProviderError,
)
from backend.ai.providers.router import AIRouter
from backend.ai.workflow.lead_brain_workflow import LeadBrainWorkflow
from backend.repositories.lead_processing_repository import LeadProcessingRepository
from backend.repositories.lead_repository import LeadRepository
from backend.services.analysis_service import AnalysisService


logger = logging.getLogger("leadforge.processing")


class LeadNotFound(Exception):
    pass


class ProcessingConflict(Exception):
    pass


class ProcessingFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class LeadProcessingService:
    def __init__(self, db: Session, provider=None):
        self.db = db
        self.provider = provider
        self.claims = LeadProcessingRepository()
        self.leads = LeadRepository(db)

    async def process(self, organization_id: int, lead_id: int) -> dict:
        # Provider work must not run inside a caller's wider DB transaction.
        if in_service_transaction(self.db):
            raise RuntimeError("Lead processing requires a standalone service operation.")
        started = monotonic()
        attempt_id = None
        try:
            with service_transaction(self.db):
                claimed = self.claims.claim(self.db, organization_id, lead_id)
                if claimed is None:
                    if self.leads.get_lead_by_id(lead_id, organization_id) is None:
                        raise LeadNotFound()
                    event("ai.analysis.conflict", organization_id=organization_id, lead_id=lead_id)
                    raise ProcessingConflict()
                lead = self.leads.get_lead_by_id(lead_id, organization_id)
                if lead is None:
                    raise LeadNotFound()
                context = {
                    "company": lead.company, "email": lead.email,
                    "source": lead.source, "industry": lead.industry,
                }
                company, email = lead.company, lead.email
            attempt_id = claimed  # Only a committed claim can need a failure write.

            provider = self.provider if self.provider is not None else AIRouter().get_provider()
            event("ai.analysis.started", organization_id=organization_id, lead_id=lead_id, provider_name=settings.AI_PROVIDER, processing_status="processing")
            result = await LeadBrainWorkflow(provider).run(context)
            decision = result.final_decision
            reason = " ".join((result.company.summary, result.contact.summary, result.intent.summary))
            with service_transaction(self.db):
                if not self.claims.complete(
                    self.db, organization_id, lead_id, attempt_id,
                    decision.lead_score, decision.priority, reason, decision.recommended_action,
                ):
                    raise ProcessingConflict()
                analysis = AnalysisService(self.db).save_analysis(
                    organization_id=organization_id, lead_id=lead_id,
                    company=company, email=email, result=result.model_dump(mode="json"),
                )
        except (LeadNotFound, ProcessingConflict):
            raise
        except Exception as exc:
            if attempt_id is not None:
                try:
                    with service_transaction(self.db):
                        self.claims.fail(self.db, organization_id, lead_id, attempt_id)
                except Exception as failure_error:
                    # Keep the original safe processing error; a failed failure
                    # marker is operational debt, not permission to hide it.
                    event("ai.analysis.failure_persistence.failed", level=logging.ERROR,
                          exc=failure_error, organization_id=organization_id, lead_id=lead_id)
            if isinstance(exc, ProviderError):
                code = exc.code
            elif isinstance(exc, ValueError):
                code = "validation_failure"
            else:
                code = "processing_failure"
            event("ai.analysis.failed", level=logging.WARNING, organization_id=organization_id, lead_id=lead_id, reason=code, processing_status="failed", duration_ms=int((monotonic()-started)*1000))
            raise ProcessingFailure(code) from exc
        event("ai.analysis.completed", organization_id=organization_id, lead_id=lead_id, analysis_id=analysis.id, provider_name=settings.AI_PROVIDER, processing_status="completed", duration_ms=int((monotonic()-started)*1000))
        return {"lead_id": lead_id, "processing_status": "completed", "analysis": analysis, "error": None}
