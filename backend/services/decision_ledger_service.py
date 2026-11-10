"""Explicit user recording, one E02 root, canonical P2-A computation only."""

from datetime import datetime, timezone

from backend.database.transactions import service_transaction
from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
from backend.repositories.lead_repository import LeadRepository
from backend.schemas.action_permission import ROLE_PERMISSIONS
from backend.schemas.decision_ledger import DecisionLedgerHistory, DecisionLedgerRecord
from backend.schemas.execution_principal import ExecutionPrincipal, PrincipalType
from backend.services.action_permission_service import ActionPermissionService
from backend.services.execution_identity import require_tenant_identity
from backend.services.opportunity_decision_service import OpportunityDecisionService
from backend.services.organization_authorization_service import OrganizationAccessDenied


class DecisionLedgerService:
    def __init__(self, db):
        self.db = db
        self.repository = DecisionLedgerRepository(db)

    def record(self, principal: ExecutionPrincipal, lead_id: int, organization_id: int):
        with service_transaction(self.db), self.db.no_autoflush:
            require_tenant_identity(principal, organization_id)
            if principal.principal_type != PrincipalType.USER:
                raise OrganizationAccessDenied()
            # No new action grant or audit taxonomy is inferred. This product
            # history command is user-only, with fresh live membership (as for
            # existing processing), plus request CSRF at the browser adapter.
            authority = ActionPermissionService(self.db).human_context(principal)
            if authority is None or authority.role not in ROLE_PERMISSIONS:
                raise OrganizationAccessDenied()
            if not self.repository.possible_lead_id(lead_id):
                return None
            # Published P1 acquisition holds one coherent stored Lead/analysis
            # context through insert. SQLite reserves its writer; PG locks row.
            if LeadRepository(self.db).get_lead_for_lifecycle_update(lead_id, organization_id) is None:
                return None
            decision = OpportunityDecisionService(self.db).get_decision(lead_id, organization_id)
            snapshot = DecisionLedgerRecord.capture(decision, datetime.now(timezone.utc))
            recorded = self.repository.append(snapshot)
        # Standalone DTO was built before settlement; never recompute on return.
        return recorded

    def history(self, lead_id, organization_id, limit=50, offset=0):
        with self.db.no_autoflush:
            if not self.repository.lead_exists(lead_id, organization_id):
                return None
            items, total = self.repository.history(organization_id, lead_id, limit, offset)
            return DecisionLedgerHistory(items=items, total=total, limit=limit, offset=offset)

    def get(self, lead_id, organization_id, decision_id):
        with self.db.no_autoflush:
            if not self.repository.lead_exists(lead_id, organization_id):
                return None
            return self.repository.get(organization_id, lead_id, decision_id)
