"""Import command history and rollback; only synthetic disposable databases."""

import base64
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import hashlib
import json
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.models import AuditEvent, Lead, Organization, OrganizationMembership, User
from backend.schemas.action_permission import ActionPermission as P
from backend.schemas.execution_principal import ExecutionPrincipal


CONTENT = b"company,email,source\nPrivate One,one@example.com,csv\nPrivate Two,two@example.com,csv\n"
SESSION_KEY = "0" * 64  # Synthetic preview signing material, never a real session.


def transaction(db):
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def import_service(db):
    # The guarded PostgreSQL fixture configures settings before this import.
    from backend.services.lead_import_service import LeadImportService
    return LeadImportService(db)


@pytest.fixture
def import_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "import-audit.db").as_posix())
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def seed_case(engine, content=CONTENT):
    suffix = uuid4().hex
    with Session(engine, autoflush=False) as db, transaction(db):
        org = Organization(name="Import owner", slug="import-" + suffix)
        foreign = Organization(name="Foreign owner", slug="foreign-" + suffix)
        user = User(email=suffix + "@example.com", password_hash="unused-synthetic-hash")
        db.add_all([org, foreign, user])
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role="member"))
        db.add(Lead(organization_id=foreign.id, company="Foreign private company",
                    email="one@example.com", source="fixture"))
        ids = dict(org=org.id, foreign_org=foreign.id, user=user.id)
    case = dict(ids=ids, content=content, principal=ExecutionPrincipal.for_user(
        ids["user"], ids["org"], correlation_id="p1e-command"))
    case["token"] = signed_token(case, content)
    return case


def signed_token(case, content, *, expires=None, organization=None, user=None):
    claims = dict(digest=hashlib.sha256(content).hexdigest(),
                  organization=organization if organization is not None else case["ids"]["org"],
                  user=user if user is not None else case["ids"]["user"],
                  expires=expires if expires is not None else int(time.time()) + 900)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    from backend.services.lead_import_service import LeadImportService
    return payload + "." + LeadImportService._signature(payload, SESSION_KEY)


def confirm(db, case, **overrides):
    kwargs = dict(principal=case["principal"], content=case["content"], token=case["token"],
                  organization_id=case["ids"]["org"], user_id=case["ids"]["user"], session_key=SESSION_KEY)
    kwargs.update(overrides)
    return import_service(db).confirm(**kwargs)


def readback(engine, case):
    with Session(engine) as observer:
        org = case["ids"]["org"]
        return (list(observer.scalars(select(Lead).where(Lead.organization_id == org))),
                list(observer.scalars(select(AuditEvent).where(AuditEvent.organization_id == org))))


def assert_summary(audit, case, summary):
    assert audit.details == summary
    assert audit.organization_id == case["ids"]["org"]
    assert audit.event_type == "business.command.completed" and audit.action == "lead.import"
    assert audit.outcome == "SUCCEEDED" and audit.reason_code == "COMMAND_COMPLETED"
    assert audit.target_type == "lead_import" and audit.target_id == audit.event_id
    assert str(UUID(audit.target_id)) == audit.target_id
    assert audit.principal_type == "USER" and audit.actor_id == str(case["ids"]["user"])
    assert audit.authority_role == "member" and audit.correlation_id == case["principal"].correlation_id
    assert audit.authorization_evidence == [dict(permission=p.value, decision="PERMIT",
        reason_code="PERMITTED_BY_ROLE") for p in (P.LEAD_IMPORT, P.LEAD_CREATE)]
    assert audit.schema_version == 1 and audit.occurred_at.tzinfo is not None
    assert audit.recorded_at >= audit.occurred_at
    for field in ("agent_id", "workflow_run_id", "integration_id", "delegated_by_type", "delegated_by_actor_id"):
        assert getattr(audit, field) is None


def test_exact_summary_uses_same_two_authorization_evaluations(import_engine, monkeypatch):
    import backend.services.action_permission_service as permission_module
    from backend.repositories.permission_repository import PermissionRepository
    from backend.services import lead_import_service as module
    case = seed_case(import_engine)
    evaluations, captures, lookups = [], [], []
    evaluate, capture, active_role = permission_module.evaluate_permission, module.capture_authorization_receipt, PermissionRepository.active_role

    def evaluated(principal, authority, permission, org):
        decision = evaluate(principal, authority, permission, org)
        evaluations.append((decision, authority))
        return decision

    def captured(principal, decision, authority):
        expected = evaluations[len(captures)]
        assert decision is expected[0] and authority is expected[1]
        captures.append(decision.permission)
        return capture(principal, decision, authority)

    def role(repo, *args):
        lookups.append(args)
        return active_role(repo, *args)

    monkeypatch.setattr(permission_module, "evaluate_permission", evaluated)
    monkeypatch.setattr(module, "capture_authorization_receipt", captured)
    monkeypatch.setattr(PermissionRepository, "active_role", role)
    before = datetime.now(timezone.utc)
    with Session(import_engine, autoflush=False) as db:
        service = import_service(db)
        assert service.repository.db is service.audit_repository.db is db
        preview = service.preview(case["content"], case["ids"]["org"], case["ids"]["user"], SESSION_KEY)
        result = confirm(db, case, token=preview.token)
    leads, audits = readback(import_engine, case)
    assert result.model_dump() == dict(total=2, imported=2, duplicates=0, invalid=0)
    assert len(leads) == 2 and len(audits) == 1
    assert_summary(audits[0], case, result.model_dump())
    assert before <= audits[0].occurred_at <= datetime.now(timezone.utc)
    assert captures == [P.LEAD_IMPORT, P.LEAD_CREATE] and len(lookups) == len(evaluations) == 2
    serialized = json.dumps({c.name: str(getattr(audits[0], c.name)) for c in AuditEvent.__table__.columns})
    for forbidden in ("Private One", "Private Two", "one@example.com", "two@example.com",
                      "Foreign private company", case["token"], preview.token, SESSION_KEY,
                      hashlib.sha256(case["content"]).hexdigest(), "company,email,source"):
        assert forbidden not in serialized
    with Session(import_engine) as db:
        assert len(list(db.scalars(select(Lead).where(Lead.organization_id == case["ids"]["foreign_org"])))) == 1
        assert list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == case["ids"]["foreign_org"]))) == []


@pytest.mark.parametrize("category", ["mixed", "all_duplicates", "all_invalid", "max_batch"])
def test_actual_batch_categories_and_noop_are_one_event(import_engine, category):
    if category == "mixed":
        content = (b"company,email,source,ignored\nPrivate One,one@example.com,csv,private note\n"
                   b"Repeated,one@example.com,csv,private note\nExisting,exists@example.com,csv,x\n"
                   b"Invalid,not-email,csv,rejected private note\nPrivate Two,two@example.com,csv,x\n")
        expected = dict(total=5, imported=2, duplicates=2, invalid=1)
    elif category == "all_duplicates":
        content = b"company,email,source\nExisting,exists@example.com,csv\nRepeated,exists@example.com,csv\n"
        expected = dict(total=2, imported=0, duplicates=2, invalid=0)
    elif category == "all_invalid":
        content = b"company,email,source\nInvalid,not-email,csv\n,other@example.com,csv\n"
        expected = dict(total=2, imported=0, duplicates=0, invalid=2)
    else:
        content = b"company,email,source\n" + b"".join(
            f"Synthetic,row{i}@example.com,csv\n".encode() for i in range(1000))
        expected = dict(total=1000, imported=1000, duplicates=0, invalid=0)
    case = seed_case(import_engine, content)
    if category in {"mixed", "all_duplicates"}:
        with Session(import_engine) as db, transaction(db):
            db.add(Lead(organization_id=case["ids"]["org"], company="Existing private",
                        email="exists@example.com", source="fixture"))
    with Session(import_engine, autoflush=False) as db:
        result = confirm(db, case)
    leads, audits = readback(import_engine, case)
    assert result.model_dump() == expected and len(audits) == 1
    assert len(leads) == expected["imported"] + (category in {"mixed", "all_duplicates"})
    assert_summary(audits[0], case, expected)
    assert len(json.dumps(audits[0].details)) < 100


def test_preview_is_read_only_and_replay_is_a_new_noop_command(import_engine):
    case = seed_case(import_engine)
    with Session(import_engine) as db:
        preview = import_service(db).preview(case["content"], case["ids"]["org"], case["ids"]["user"], SESSION_KEY)
    assert readback(import_engine, case) == ([], [])
    with Session(import_engine, autoflush=False) as db:
        first = confirm(db, case, token=preview.token)
        second = confirm(db, case, token=preview.token)
    leads, audits = readback(import_engine, case)
    assert len(leads) == 2 and len(audits) == 2
    assert len({a.event_id for a in audits}) == 2
    assert first.imported == 2 and second.imported == 0 and second.duplicates == 2
    assert sorted((a.details["imported"], a.details["duplicates"]) for a in audits) == [(0, 2), (2, 0)]


@pytest.mark.parametrize("content", [b"", b"company,email,source\n", b"company,email,source\n,,\n",
    b"wrong,headers\nx,y\n", b"company,email,source\nBad,\x00,csv\n", b"company,email,source\n\xff\n"])
def test_rejected_file_creates_no_success_or_denial_audit(import_engine, content):
    from backend.services.lead_import_service import ImportValidationError
    case = seed_case(import_engine, content)
    with Session(import_engine, autoflush=False) as db:
        with pytest.raises(ImportValidationError):
            confirm(db, case)
    assert readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("failure", ["signature", "changed_file", "session", "expired", "token_tenant", "token_user"])
def test_preview_guards_leave_no_business_or_audit(import_engine, failure):
    from backend.services.lead_import_service import ImportValidationError
    case = seed_case(import_engine)
    overrides = {}
    if failure == "signature": overrides["token"] = "invalid.invalid"
    elif failure == "changed_file": overrides["content"] = CONTENT + b"Extra,extra@example.com,csv\n"
    elif failure == "session": overrides["session_key"] = "1" * 64
    elif failure == "expired": overrides["token"] = signed_token(case, CONTENT, expires=1)
    elif failure == "token_tenant": overrides["token"] = signed_token(case, CONTENT, organization=case["ids"]["foreign_org"])
    else: overrides["token"] = signed_token(case, CONTENT, user=case["ids"]["user"] + 10000)
    with Session(import_engine, autoflush=False) as db:
        with pytest.raises(ImportValidationError, match="Preview expired or file changed"):
            confirm(db, case, **overrides)
    assert readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("denial", ["inactive", "import_permission", "create_permission", "tenant", "identity", "user_mismatch"])
def test_authorization_and_tenant_failures_have_no_audit(import_engine, monkeypatch, denial):
    from backend.core.exceptions import LeadForgeException
    from backend.schemas.action_permission import ROLE_PERMISSIONS
    from backend.services.lead_import_service import ImportValidationError
    case = seed_case(import_engine)
    overrides = {}
    if denial == "inactive":
        with Session(import_engine) as db, transaction(db):
            db.scalar(select(OrganizationMembership).where(
                OrganizationMembership.organization_id == case["ids"]["org"],
                OrganizationMembership.user_id == case["ids"]["user"])).is_active = False
    elif denial in {"import_permission", "create_permission"}:
        import backend.services.action_permission_service as authority_service
        import backend.services.permission_evaluator as evaluator
        missing = P.LEAD_IMPORT if denial == "import_permission" else P.LEAD_CREATE
        policy = {"member": ROLE_PERMISSIONS["member"] - {missing}}
        monkeypatch.setattr(authority_service, "ROLE_PERMISSIONS", policy)
        monkeypatch.setattr(evaluator, "ROLE_PERMISSIONS", policy)
    elif denial == "tenant": overrides["organization_id"] = case["ids"]["foreign_org"]
    elif denial == "identity": overrides["principal"] = None
    else: overrides["user_id"] = case["ids"]["user"] + 10000
    with Session(import_engine, autoflush=False) as db:
        with pytest.raises(ImportValidationError if denial == "user_mismatch" else LeadForgeException):
            confirm(db, case, **overrides)
    assert readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("kind", ["SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
def test_session_bound_import_still_rejects_machine_actors(import_engine, kind):
    from backend.services.lead_import_service import ImportValidationError
    case = seed_case(import_engine)
    principal = getattr(ExecutionPrincipal, "for_" + kind.lower())("synthetic-" + kind.lower(), case["ids"]["org"])
    with Session(import_engine, autoflush=False) as db:
        with pytest.raises(ImportValidationError, match="Import identity mismatch"):
            confirm(db, case, principal=principal)
    assert readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("failure", ["constraint", "exception"])
def test_fatal_second_row_rolls_back_released_first_savepoint(import_engine, monkeypatch, failure):
    from backend.repositories.lead_import_repository import LeadImportRepository
    case = seed_case(import_engine)
    original, calls = LeadImportRepository.add, []
    def fail_second(repo, org, company, email, source):
        calls.append(email)
        if len(calls) == 2:
            assert repo.db.scalar(select(Lead.id).where(Lead.organization_id == org, Lead.email == "one@example.com"))
            assert readback(import_engine, case) == ([], [])
            if failure == "exception": raise RuntimeError("Synthetic row failure")
            company = None
        return original(repo, org, company, email, source)
    monkeypatch.setattr(LeadImportRepository, "add", fail_second)
    with Session(import_engine, autoflush=False) as db:
        with pytest.raises(IntegrityError if failure == "constraint" else RuntimeError):
            confirm(db, case)
    assert len(calls) == 2 and readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("failure", ["construction", "append", "constraint"])
def test_audit_failure_rolls_back_entire_flushed_batch(import_engine, monkeypatch, failure):
    from backend.repositories.audit_repository import AuditRepository
    from backend.schemas.audit_event import AuditValidationError
    from backend.services.audit_event_builder import AuditEventBuilder
    case = seed_case(import_engine)
    with Session(import_engine, autoflush=False) as db:
        observations = []
        def see_batch():
            assert len(list(db.scalars(select(Lead).where(Lead.organization_id == case["ids"]["org"])))) == 2
            assert readback(import_engine, case) == ([], [])
            observations.append(True)
        def construct(*_args, **_kwargs):
            see_batch()
            raise AuditValidationError("Synthetic audit construction failure")
        def append(repo, _draft):
            assert repo.db is db
            see_batch()
            raise RuntimeError("Synthetic audit append failure")
        def constraint(_mapper, _connection, audit):
            see_batch()
            audit.schema_version = 0  # Exercise the actual database CHECK.
        if failure == "construction": monkeypatch.setattr(AuditEventBuilder, "import_completed", construct)
        elif failure == "append": monkeypatch.setattr(AuditRepository, "append", append)
        else: event.listen(AuditEvent, "before_insert", constraint)
        try:
            with pytest.raises({"construction": AuditValidationError, "append": RuntimeError,
                                "constraint": IntegrityError}[failure]):
                confirm(db, case)
        finally:
            if failure == "constraint": event.remove(AuditEvent, "before_insert", constraint)
        assert observations == [True] and db.is_active
    assert readback(import_engine, case) == ([], [])


@pytest.mark.parametrize("failure", ["outer", "caught_nested", "savepoint_release", "commit"])
def test_outer_root_owns_business_and_audit_durability(import_engine, monkeypatch, failure):
    from backend.database.transactions import TransactionAborted, service_savepoint
    case = seed_case(import_engine)
    with Session(import_engine, autoflush=False) as db:
        if failure == "commit":
            def reject_commit(): raise RuntimeError("Synthetic settlement failure")
            monkeypatch.setattr(db, "commit", reject_commit)
        with pytest.raises(TransactionAborted if failure == "caught_nested" else RuntimeError):
            with transaction(db):
                result = confirm(db, case)
                assert result.imported == 2
                assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == case["ids"]["org"])))) == 1
                assert readback(import_engine, case) == ([], [])
                if failure == "savepoint_release":
                    with service_savepoint(db):
                        db.add(Lead(organization_id=case["ids"]["org"], company="Subordinate",
                                    email="subordinate@example.com", source="test"))
                        db.flush()
                    assert readback(import_engine, case) == ([], [])
                if failure == "caught_nested":
                    try:
                        with transaction(db): raise ValueError("Nested failure")
                    except ValueError: pass
                elif failure != "commit": raise RuntimeError("Synthetic outer failure")
    assert readback(import_engine, case) == ([], [])


def test_result_mutation_does_not_change_immutable_summary(import_engine, monkeypatch):
    from backend.services.audit_event_builder import AuditEventBuilder
    case = seed_case(import_engine)
    drafts, build = [], AuditEventBuilder.import_completed
    def capture(*args, **kwargs):
        draft = build(*args, **kwargs)
        drafts.append(draft)
        return draft
    monkeypatch.setattr(AuditEventBuilder, "import_completed", capture)
    with Session(import_engine, autoflush=False) as db, transaction(db):
        result = confirm(db, case)
        result.imported = 0
        with pytest.raises(FrozenInstanceError): drafts[0].details.imported = 0
        copied = drafts[0].details.as_json()
        copied["imported"] = 0
    leads, audits = readback(import_engine, case)
    assert len(leads) == 2 and len(audits) == 1
    assert_summary(audits[0], case, dict(total=2, imported=2, duplicates=0, invalid=0))


@pytest.mark.parametrize("audit_failure", [False, True])
def test_http_confirmation_uses_atomic_import_audit(tenant_workspace, monkeypatch, audit_failure):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database.session import SessionLocal
    from backend.repositories.audit_repository import AuditRepository
    from tests.api.test_tenant_leads import headers
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    h = {**headers(workspace, "a", csrf=True), "Content-Type": "text/csv", "X-Request-ID": "p1e-http", "X-Role": "admin"}
    preview = client.post("/api/imports/leads/preview", headers=h, content=CONTENT)
    assert preview.status_code == 200
    if audit_failure:
        def fail(*_args): raise RuntimeError("Synthetic route audit failure")
        monkeypatch.setattr(AuditRepository, "append", fail)
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as request_client:
        request_client.cookies.update(client.cookies)
        response = request_client.post("/api/imports/leads/confirm", content=CONTENT,
            headers={**h, "X-Import-Preview-Token": preview.json()["token"]})
    assert response.status_code == (500 if audit_failure else 200)
    org = workspace["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        imported = list(db.scalars(select(Lead).where(Lead.organization_id == org,
                                   Lead.email.in_(["one@example.com", "two@example.com"]))))
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == org,
                                AuditEvent.correlation_id == "p1e-http")))
        if audit_failure: assert imported == audits == []
        else:
            assert len(imported) == 2 and len(audits) == 1
            assert audits[0].details == response.json() == dict(total=2, imported=2, duplicates=0, invalid=0)
            assert audits[0].actor_id == str(workspace["ids"]["users"]["a"])
            assert audits[0].authority_role == "owner" and audits[0].action == "lead.import"
