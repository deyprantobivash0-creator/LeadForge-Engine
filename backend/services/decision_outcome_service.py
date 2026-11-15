"""Human feedback only: no lifecycle mutation, scoring, learning or external action."""
from datetime import datetime, timezone
from uuid import uuid4
from backend.database.transactions import service_transaction
from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
from backend.repositories.decision_outcome_repository import DecisionOutcomeRepository
from backend.schemas.action_permission import ROLE_PERMISSIONS
from backend.schemas.decision_outcome import OutcomeHistory, OutcomeInput
from backend.schemas.execution_principal import PrincipalType
from backend.services.action_permission_service import ActionPermissionService
from backend.services.execution_identity import require_tenant_identity
from backend.services.organization_authorization_service import OrganizationAccessDenied


class OutcomeTimeError(ValueError):
    pass


class DecisionOutcomeService:
    def __init__(self, db):
        self.db = db
        self.ledger = DecisionLedgerRepository(db)
        self.repository = DecisionOutcomeRepository(db)

    def history(self, lead_id, decision_id, org, limit=20, offset=0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000000:
            raise ValueError("Invalid outcome pagination.")
        with self.db.no_autoflush:
            if not self.ledger.possible_lead_id(lead_id) or self.ledger.get(org, lead_id, decision_id) is None:
                return None
            rows, total, latest = self.repository.history(org, lead_id, decision_id, limit, offset)
            label = ("Outcome pending" if latest is None else "Negative outcome" if latest == "Lost"
                     else "Inconclusive" if latest == "Contacted" else "Positive outcome")
            return OutcomeHistory(items=rows, total=total, limit=limit, offset=offset, effectiveness=label)

    def record(self, principal, lead_id, decision_id, org, payload):
        payload = OutcomeInput.model_validate(payload)
        with service_transaction(self.db), self.db.no_autoflush:
            require_tenant_identity(principal, org)
            if principal.principal_type != PrincipalType.USER:
                raise OrganizationAccessDenied()
            authority = ActionPermissionService(self.db).human_context(principal)
            if authority is None or authority.role not in ROLE_PERMISSIONS:
                raise OrganizationAccessDenied()
            if not self.ledger.possible_lead_id(lead_id):
                return None
            decision = self.ledger.get(org, lead_id, decision_id)
            if decision is None:
                return None
            now = datetime.now(timezone.utc)
            if not decision.recorded_at <= payload.observed_at <= now:
                raise OutcomeTimeError("Observation must follow the recorded decision and cannot be in the future.")
            return self.repository.append(dict(id=str(uuid4()), organization_id=org, lead_id=lead_id,
                decision_id=str(decision_id), kind=payload.kind.value, observed_at=payload.observed_at,
                recorded_at=now, recorded_by_user_id=int(principal.actor_id), note=payload.note))
