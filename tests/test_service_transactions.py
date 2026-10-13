"""Disposable databases prove commit ownership and all-or-nothing commands."""

import asyncio
import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.database.transactions import TransactionAborted, service_transaction
from backend.models import Lead, LeadAnalysis, Organization, User, OrganizationMembership
from backend.schemas.execution_principal import ExecutionPrincipal
from backend.schemas.action_permission import ActionPermission as P, MachineAuthorizationContext
from backend.repositories.lead_repository import LeadRepository
from backend.services.analysis_service import AnalysisService
from backend.services.lead_import_service import LeadImportService
from backend.services.lead_lifecycle_service import LeadLifecycleService
from backend.services.lead_processing_service import LeadProcessingService, ProcessingFailure
from backend.services.lead_service import LeadService
from backend.ai.providers.mock_provider import MockProvider


@pytest.fixture
def command_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'commands.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        db.add_all([Organization(id=1, name="One", slug="one"),
                    Organization(id=2, name="Two", slug="two")])
        db.commit()
        yield db
    engine.dispose()


def commit_spy(db, monkeypatch):
    calls = []
    original = db.commit

    def commit():
        calls.append("commit")
        return original()

    monkeypatch.setattr(db, "commit", commit)
    return calls


def persisted_leads(db):
    with Session(db.get_bind()) as observer:
        return [(lead.email, lead.status) for lead in observer.scalars(select(Lead))]


def create(db, email="new@example.com", organization_id=1):
    principal = ExecutionPrincipal.for_system("test-fixture", organization_id)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    return LeadService(db).create_lead(principal, company="Synthetic", email=email,
                                     source="test", organization_id=organization_id,
                                     machine_context=context)


def lifecycle(db, lead_id, organization_id, status):
    principal = ExecutionPrincipal.for_system("test-fixture", organization_id)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_LIFECYCLE_CHANGE}))
    return LeadLifecycleService(db).update_lifecycle(principal, lead_id=lead_id,
        organization_id=organization_id, status=status, machine_context=context)


def test_successful_command_commits_once(command_db, monkeypatch):
    calls = commit_spy(command_db, monkeypatch)
    lead = create(command_db)
    assert lead.id and calls == ["commit"]
    assert persisted_leads(command_db) == [("new@example.com", "New")]


@pytest.mark.parametrize("mutation", ["create", "status", "lifecycle"])
def test_repository_flushes_without_commit_or_rollback(command_db, monkeypatch, mutation):
    db = command_db
    lead_id = create(db).id
    db.rollback()  # End post-command attribute read.
    calls = commit_spy(db, monkeypatch)
    original_rollback = db.rollback
    monkeypatch.setattr(db, "rollback", lambda: pytest.fail("Repository rolled back"))
    repository = LeadRepository(db)
    if mutation == "create":
        result = repository.create_lead(Lead(organization_id=1, company="Two",
                                             email="two@example.com", source="test"))
    elif mutation == "status":
        result = repository.update_status(lead_id, 1, "Contacted")
    else:
        result = repository.update_lifecycle(lead_id, 1, notes="Synthetic note")
    assert result.id and calls == []
    original_rollback()
    assert persisted_leads(db) == [("new@example.com", "New")]


def test_nested_service_commands_share_one_commit(command_db, monkeypatch):
    calls = commit_spy(command_db, monkeypatch)
    with service_transaction(command_db):
        lead = create(command_db)
        lifecycle(command_db, lead.id, 1, "Contacted")
        assert calls == []
    assert calls == ["commit"]
    assert persisted_leads(command_db) == [("new@example.com", "Contacted")]


@pytest.mark.parametrize("failure", ["unexpected", "validation", "database"])
def test_outer_failure_rolls_back_early_nested_write(command_db, failure):
    expected = {"unexpected": RuntimeError, "validation": ValueError,
                "database": IntegrityError}[failure]
    with pytest.raises(expected):
        with service_transaction(command_db):
            lead = create(command_db)
            if failure == "unexpected":
                raise RuntimeError("Synthetic command failure")
            if failure == "validation":
                lifecycle(command_db, lead.id, 1, "invalid")
            else:
                create(command_db, organization_id=999)
    assert persisted_leads(command_db) == []
    assert not command_db.in_transaction()


def test_caught_inner_failure_marks_outer_rollback_only(command_db):
    with pytest.raises(TransactionAborted):
        with service_transaction(command_db):
            lead = create(command_db)
            try:
                lifecycle(command_db, lead.id, 1, "invalid")
            except ValueError:
                pass
    assert persisted_leads(command_db) == []
    # Failure state is removed, allowing a fresh command.
    create(command_db, "fresh@example.com")
    assert persisted_leads(command_db) == [("fresh@example.com", "New")]


def test_commit_failure_rolls_back_flushed_changes(command_db, monkeypatch):
    def fail():
        command_db.flush()
        raise RuntimeError("Synthetic commit failure")

    monkeypatch.setattr(command_db, "commit", fail)
    with pytest.raises(RuntimeError):
        create(command_db)
    assert persisted_leads(command_db) == []


def test_rollback_failure_preserves_original_and_logs_safely(command_db, monkeypatch, caplog):
    original = ValueError("Original command failure")

    def fail():
        raise RuntimeError("Synthetic private rollback details")

    monkeypatch.setattr(command_db, "rollback", fail)
    with pytest.raises(ValueError) as caught:
        with service_transaction(command_db):
            create(command_db)
            raise original
    assert caught.value is original
    assert "transaction.rollback.failed" in caplog.text
    assert "Synthetic private rollback details" not in caplog.text
    assert persisted_leads(command_db) == []


def test_lifecycle_cannot_mutate_another_tenant(command_db):
    lead_id = create(command_db, organization_id=2).id
    assert lifecycle(command_db, lead_id, 1, "Contacted") is None
    with Session(command_db.get_bind()) as observer:
        assert observer.get(Lead, lead_id).organization_id == 2
        assert observer.get(Lead, lead_id).status == "New"


def test_query_service_does_not_commit_or_flush(command_db, monkeypatch):
    lead_id = create(command_db).id
    calls = commit_spy(command_db, monkeypatch)
    monkeypatch.setattr(command_db, "flush", lambda *args, **kwargs: pytest.fail("Query flushed"))
    service = LeadService(command_db)
    assert service.get_lead(lead_id, 1).email == "new@example.com"
    assert service.get_lead(lead_id, 2) is None
    assert service.get_leads(1)[1] == 1
    assert calls == [] and not command_db.new and not command_db.dirty


CSV = b"company,email,source\nOne,one@example.com,test\nTwo,two@example.com,test\n"


def import_command(db):
    # Confirmation is a human/session operation: seed only the current member.
    db.add(User(id=1, email="import-human@example.com", password_hash="unused-test-hash"))
    db.flush()
    db.add(OrganizationMembership(user_id=1, organization_id=1, role="member"))
    db.commit()
    service = LeadImportService(db)
    # Synthetic session signing material; never a real session/credential.
    signing_key = "0" * 64
    token = service.preview(CSV, 1, 1, signing_key).token
    return service, token, signing_key


def test_csv_success_commits_batch_once(command_db, monkeypatch):
    service, token, key = import_command(command_db)
    calls = commit_spy(command_db, monkeypatch)
    assert service.confirm(ExecutionPrincipal.for_user(1, 1), CSV, token, 1, 1, key).imported == 2
    assert calls == ["commit"]
    assert len(persisted_leads(command_db)) == 2


def test_csv_failure_rolls_back_released_early_savepoint(command_db, monkeypatch):
    service, token, key = import_command(command_db)
    original = service.repository.add
    count = 0

    def add(*args):
        nonlocal count
        count += 1
        result = original(*args)
        if count == 2:
            raise RuntimeError("Synthetic second row failure")
        return result

    monkeypatch.setattr(service.repository, "add", add)
    with pytest.raises(RuntimeError):
        service.confirm(ExecutionPrincipal.for_user(1, 1), CSV, token, 1, 1, key)
    assert count == 2 and persisted_leads(command_db) == []


def test_nested_csv_and_later_failure_roll_back_entire_batch(command_db):
    service, token, key = import_command(command_db)
    with pytest.raises(ValueError):
        with service_transaction(command_db):
            assert service.confirm(ExecutionPrincipal.for_user(1, 1), CSV, token, 1, 1, key).imported == 2
            raise ValueError("Later business validation failed")
    assert persisted_leads(command_db) == []


def test_dependency_closes_without_commit_and_propagates_error(monkeypatch):
    from backend.database import dependencies

    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    db = FakeSession()
    monkeypatch.setattr(dependencies, "SessionLocal", lambda: db)
    dependency = dependencies.get_db()
    assert next(dependency) is db
    with pytest.raises(ValueError):
        dependency.throw(ValueError("Synthetic HTTP failure"))
    assert db.closed


def test_auth_nested_login_commits_once_and_outer_failure_rolls_back(tenant_workspace, monkeypatch):
    from backend.database.session import SessionLocal
    from backend.models import AuthSession
    from backend.services.authentication_service import AuthenticationService

    with SessionLocal() as db:
        calls = commit_spy(db, monkeypatch)
        AuthenticationService(db).login("user-a@example.com", "tenant fixture password")
        assert calls == ["commit"]  # login -> create_session is one boundary.
        before = set(db.scalars(select(AuthSession.id)))
        with pytest.raises(ValueError):
            with service_transaction(db):
                AuthenticationService(db).login("user-a@example.com", "tenant fixture password")
                raise ValueError("Synthetic later command failure")
        assert set(db.scalars(select(AuthSession.id))) == before
        assert calls == ["commit"]


def test_processing_completion_and_analysis_rollback_together(command_db, monkeypatch):
    lead_id = create(command_db).id
    original = AnalysisService.save_analysis

    def fail_after_analysis(self, **kwargs):
        original(self, **kwargs)
        raise RuntimeError("Synthetic post-analysis failure")

    monkeypatch.setattr(AnalysisService, "save_analysis", fail_after_analysis)
    with pytest.raises(ProcessingFailure) as caught:
        asyncio.run(LeadProcessingService(command_db, MockProvider()).process(1, lead_id))
    assert caught.value.code == "processing_failure"
    with Session(command_db.get_bind()) as observer:
        lead = observer.get(Lead, lead_id)
        assert lead.processing_status == "failed" and lead.lead_score is None
        assert list(observer.scalars(select(LeadAnalysis))) == []


def test_processing_failure_marker_failure_preserves_original(command_db, monkeypatch, caplog):
    from backend.ai.providers.base import ProviderMalformedOutput

    class BrokenProvider(MockProvider):
        async def generate(self, prompt):
            raise ProviderMalformedOutput("Synthetic provider failure")

    lead_id = create(command_db).id
    service = LeadProcessingService(command_db, BrokenProvider())

    def fail(*args):
        raise RuntimeError("Synthetic private database failure")

    monkeypatch.setattr(service.claims, "fail", fail)
    with pytest.raises(ProcessingFailure) as caught:
        asyncio.run(service.process(1, lead_id))
    assert caught.value.code == "malformed_provider_output"
    assert isinstance(caught.value.__cause__, ProviderMalformedOutput)
    assert "ai.analysis.failure_persistence.failed" in caplog.text
    assert "Synthetic private database failure" not in caplog.text
    assert not command_db.in_transaction()


def test_processing_cannot_commit_an_outer_service_command(command_db):
    with pytest.raises(RuntimeError):
        with service_transaction(command_db):
            lead = create(command_db)
            asyncio.run(LeadProcessingService(command_db, MockProvider()).process(1, lead.id))
    assert persisted_leads(command_db) == []


def test_repositories_and_routes_have_no_transaction_ownership():
    root = Path(__file__).resolve().parents[1] / "backend"
    for folder in (root / "repositories", root / "api" / "routes"):
        for path in folder.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                           and node.func.attr in {"commit", "rollback"}
                           for node in ast.walk(tree)), path.name
