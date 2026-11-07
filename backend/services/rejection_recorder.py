"""One bounded synchronous attempt; explicit persistence knowledge, no retry."""

from contextvars import Context
from dataclasses import dataclass, field
from enum import StrEnum
import sqlite3
from threading import Lock
from weakref import WeakValueDictionary, ref

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database.rejection_storage import Attempt, attempt_scope, create_rejection_storage
from backend.repositories.audit_repository import AuditRepository
from backend.schemas.audit_event import AuditEventReceipt, AuditValidationError
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.services.application_audit import (
    SettledRejection, _application_audit_transaction, rejection_diagnostic, validate_settlement,
    validate_rejection,
)


class RejectionPersistenceStatus(StrEnum):
    RECORDED = "RECORDED"
    NOT_RECORDED = "NOT_RECORDED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True)
class RejectionRecordingResult:
    """Event knowledge, with this invocation's separate observation if attempted."""
    status: RejectionPersistenceStatus
    settlement: SettledRejection | None = None
    receipt: AuditEventReceipt | None = None
    attempt_status: RejectionPersistenceStatus | None = None


@dataclass(eq=False)
class _EventKnowledge:
    """Evidence retained by live sealed handles, never durable/shared recovery.

    Fields only move toward stronger knowledge: uncertainty is sticky and a
    receipt is never cleared. No Session/Engine/request or business authority.
    The non-waiting lock prevents overlapping same-event persistence attempts.
    """
    owner: object
    identity: tuple
    uncertain: bool = False
    receipt: AuditEventReceipt | None = None
    operation: object = field(default_factory=Lock, repr=False)


class RejectionRecorder:
    def __init__(self, session_factory, *, canonical_connect_args=None, canonical_connections=()):
        if (not isinstance(session_factory, sessionmaker)
                or not isinstance(session_factory.kw.get("bind"), Engine)
                or session_factory.kw.get("twophase", False)):
            raise ValueError("Canonical Engine-bound Session factory required.")
        self._session_factory = session_factory
        self._session_class = session_factory.class_
        self._database_bind = session_factory.kw["bind"]
        self._recording_key = object()
        # Weak values: only live boundary-minted handles retain evidence. This
        # index is local to this owner, not a global cache or crash/worker store.
        self._event_knowledge = WeakValueDictionary()
        self._draft_knowledge = {}
        self._knowledge_mint_lock = Lock()
        self._storage = create_rejection_storage(
            self.database_bind, canonical_connect_args=canonical_connect_args,
            canonical_connections=canonical_connections)

    @property
    def database_bind(self):
        return self._database_bind

    def close(self):
        """Application owner releases the recorder-only idle pool at shutdown."""
        self._storage.audit_bind.dispose()

    def _new_event_knowledge(self, draft):
        """Bind a capsule while minting settlement, outside recorder invocation."""
        validate_rejection(draft)
        identity = (draft.principal.organization_id, draft.event_id, draft._seal)
        if not self._knowledge_mint_lock.acquire(blocking=False):
            raise AuditValidationError("Sealed event knowledge binding unavailable.")
        try:
            knowledge = self._event_knowledge.get(identity)
            if knowledge is None:
                knowledge = _EventKnowledge(self._recording_key, identity)
                self._event_knowledge[identity] = knowledge
            # Keep evidence while any original sealed draft or settlement is
            # live, without retaining the draft itself or growing a history.
            draft_id = id(draft)
            binding = self._draft_knowledge.get(draft_id)
            if binding is None or binding[0]() is not draft:
                owner = ref(self)
                def released(weak_draft):
                    recorder = owner()
                    if recorder is not None:
                        current = recorder._draft_knowledge.get(draft_id)
                        if current is not None and current[0] is weak_draft:
                            recorder._draft_knowledge.pop(draft_id, None)
                self._draft_knowledge[draft_id] = (ref(draft, released), knowledge)
            return knowledge
        finally:
            self._knowledge_mint_lock.release()

    def _validated_knowledge(self, record):
        knowledge = record._knowledge
        identity = (record.draft.principal.organization_id, record.draft.event_id, record.draft._seal)
        if (type(knowledge) is not _EventKnowledge or knowledge.owner is not self._recording_key
                or knowledge.identity != identity):
            raise AuditValidationError("Sealed event knowledge provenance required.")
        return knowledge

    @staticmethod
    def _event_result(record, knowledge, attempt_status=None):
        # One-way evidence fields make RECORDED absorbing, even if another
        # same-event caller encountered a failure or could not acquire the lock.
        receipt = knowledge.receipt
        status = (RejectionPersistenceStatus.RECORDED if receipt is not None else
                  RejectionPersistenceStatus.OUTCOME_UNKNOWN if knowledge.uncertain else
                  RejectionPersistenceStatus.NOT_RECORDED)
        return RejectionRecordingResult(status, record, receipt, attempt_status)

    def record_after_settlement(self, record):
        # Start before validation, Context construction and Session work.
        state = Attempt()
        return Context().run(self._run, record, state, False, None)

    def reconcile_rejection(self, record, tenant_context):
        """Explicit internal scoped read; absence after UNKNOWN stays UNKNOWN.

        Authenticated caller supplies trusted tenant context and the original
        boundary-minted material. This is not an HTTP replay endpoint.
        """
        state = Attempt()
        return Context().run(self._run, record, state, True, tenant_context)

    def _run(self, record, state, read_only, tenant_context):
        valid = False
        knowledge = None
        acquired = False
        try:
            with attempt_scope(state):
                # Validate before observing capsule state, including on expired
                # replays. This is bounded sealed data, not a DB/cache lookup.
                validate_settlement(record, self._recording_key)
                if read_only:
                    if type(tenant_context) is not ExecutionPrincipal:
                        raise ValueError("Trusted tenant context required.")
                    tenant_context = ExecutionPrincipal.model_validate(tenant_context)
                    if tenant_context.organization_id != record.draft.principal.organization_id:
                        return RejectionRecordingResult(RejectionPersistenceStatus.OUTCOME_UNKNOWN)
                knowledge = self._validated_knowledge(record)
                valid = True
                if knowledge.receipt is not None:
                    return self._event_result(record, knowledge)
                acquired = knowledge.operation.acquire(blocking=False)
                if not acquired:
                    knowledge.uncertain = True
                    return self._event_result(record, knowledge)
                try:
                    state.remaining()
                    if (self._session_factory.kw.get("bind") is not self.database_bind
                            or self._session_factory.class_ is not self._session_class):
                        raise ValueError("Audit factory changed.")
                    self._persist(record, state, read_only)
                except Exception as exc:
                    if isinstance(exc, IntegrityError):
                        origin = exc.orig
                        state.uncertain = (
                            getattr(origin, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY
                            or (getattr(origin, "sqlstate", None) == "23505"
                                and getattr(getattr(origin, "diag", None), "constraint_name", None)
                                == "pk_audit_events"))
                    rejection_diagnostic("audit.rejection.persistence_failed", record.draft)
                attempt_status = (RejectionPersistenceStatus.RECORDED
                    if state.acknowledged and state.receipt is not None else
                    RejectionPersistenceStatus.OUTCOME_UNKNOWN
                    if read_only or (state.commit_started and not state.known_rollback) or state.uncertain else
                    RejectionPersistenceStatus.NOT_RECORDED)
                if attempt_status is RejectionPersistenceStatus.OUTCOME_UNKNOWN:
                    knowledge.uncertain = True
                if (attempt_status is RejectionPersistenceStatus.RECORDED
                        and (read_only or not knowledge.uncertain)):
                    knowledge.receipt = state.receipt
                # A replay ACK is attempt evidence; prior UNKNOWN is resolved
                # only by the separately invoked tenant-scoped reconciliation.
                return self._event_result(record, knowledge, attempt_status)
        except Exception:
            rejection_diagnostic("audit.rejection.persistence_failed", record.draft if valid else None)
            if valid and knowledge is not None:
                knowledge.uncertain = True
                return self._event_result(record, knowledge)
            return RejectionRecordingResult(RejectionPersistenceStatus.OUTCOME_UNKNOWN if read_only
                                             else RejectionPersistenceStatus.NOT_RECORDED)
        finally:
            if acquired:
                knowledge.operation.release()

    def _persist(self, record, state, read_only=False):
        with _application_audit_transaction(self._session_factory, record, self._storage) as audit_db:
            repo = AuditRepository(audit_db)
            if read_only:
                state.receipt = repo._get_matching_event(record.draft)
                state.acknowledged = state.receipt is not None
            else:
                state.receipt = repo.append(record.draft)
