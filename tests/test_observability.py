"""Operational semantics, correlation and synthetic privacy checks."""
import asyncio
import json
import logging
import traceback
import uuid
import warnings
import pytest
from fastapi.testclient import TestClient
from backend.core.config import settings
from backend.core.error_handlers import generic_exception_handler
from backend.core.logger import JsonFormatter, event, request_id_context
from backend.main import ObservedFastAPI


@pytest.mark.parametrize('incoming', [None, 'synthetic-request-5d', 'bad value', 'x'*65])
def test_request_id_response_and_log(client, caplog, incoming):
    with caplog.at_level(logging.DEBUG):
        response=client.get('/health?private=DO_NOT_LOG', headers={} if incoming is None else {'X-Request-ID':incoming})
    correlation=response.headers['X-Request-ID']
    assert correlation == incoming if incoming == 'synthetic-request-5d' else len(correlation)==32
    records=[record for record in caplog.records if getattr(record,'event',None)=='http.request.completed']
    assert len(records)==1
    record=records[-1]
    assert record.request_id == correlation
    assert record.path == '/health' and record.status_code == 200 and record.duration_ms >= 0
    assert 'DO_NOT_LOG' not in JsonFormatter().format(record)
    assert request_id_context.get() is None


def test_unhandled_error_is_correlated_private_and_actionable(caplog):
    sentinel='synthetic-'+uuid.uuid4().hex
    app=ObservedFastAPI()
    app.add_exception_handler(Exception,generic_exception_handler)
    @app.get('/failure/{item}')
    def fail(item:str):
        raise RuntimeError(sentinel+' password cookie csrf lead@example.com')
    with caplog.at_level(logging.DEBUG), TestClient(app,raise_server_exceptions=False) as client:
        response=client.get('/failure/'+sentinel,headers={'X-Request-ID':'synthetic-failure-id'})
    assert response.status_code==500 and response.headers['X-Request-ID']=='synthetic-failure-id'
    assert sentinel not in response.text and 'Traceback' not in response.text
    records=[record for record in caplog.records if getattr(record,'event',None)=='http.exception']
    assert records[-1].request_id=='synthetic-failure-id'
    assert records[-1].exception_type=='RuntimeError' and records[-1].stack
    rendered=[JsonFormatter().format(record) for record in caplog.records]
    assert sentinel not in '\n'.join(rendered) and 'lead@example.com' not in '\n'.join(rendered)
    request=[record for record in caplog.records if getattr(record,'event',None)=='http.request.failed'][-1]
    assert request.path=='/failure/{item}' and request.status_code==500


def test_duplicate_ids_and_unknown_paths_do_not_leak(client,caplog):
    with caplog.at_level(logging.INFO):
        response=client.get('/unknown-secret-email@example.com',headers=[('X-Request-ID','first'),('X-Request-ID','second')])
    assert response.status_code==404 and response.headers['X-Request-ID'] not in {'first','second'}
    record=[record for record in caplog.records if getattr(record,'event',None)=='http.request.completed'][-1]
    assert record.path=='<unmatched>'


def test_slow_request_signal(client,caplog,monkeypatch):
    monkeypatch.setattr(settings,'SLOW_REQUEST_MS',1)
    from backend.core import request_logging
    values=iter([10.0,10.1])
    monkeypatch.setattr(request_logging,'perf_counter',lambda:next(values))
    with caplog.at_level(logging.INFO):client.get('/health')
    record=[record for record in caplog.records if getattr(record,'event',None)=='http.request.slow'][-1]
    assert record.duration_ms==100 and record.levelno==logging.WARNING


def test_json_redaction_and_third_party_exception_privacy(monkeypatch):
    sentinel='synthetic-'+uuid.uuid4().hex
    monkeypatch.setattr(settings,'GEMINI_API_KEY',sentinel)
    record=logging.LogRecord('third.party',logging.ERROR,__file__,1,'email=private@example.com password=%s',(sentinel,),None)
    data=json.loads(JsonFormatter().format(record))
    assert data['message']=='Runtime diagnostic'
    record.event='test.safe'
    record.path='postgresql+psycopg://user:'+sentinel+'@db.internal/app'
    rendered=JsonFormatter().format(record)
    assert sentinel not in rendered and json.loads(rendered)['path']=='[REDACTED URL]'
    assert data['timestamp'].endswith('Z') and data['service']=='leadforge-backend'
    record.event='migration.started'
    assert json.loads(JsonFormatter().format(record))['service']=='leadforge-migration'


def test_auth_body_cookie_and_csrf_are_never_logged(client,caplog):
    sentinel='synthetic-'+uuid.uuid4().hex
    with caplog.at_level(logging.DEBUG):
        response=client.post('/api/auth/login',json={'email':'synthetic-private@example.com','password':sentinel},
                             headers={'Cookie':'session='+sentinel,'X-CSRF-Token':sentinel,'Authorization':'Bearer '+sentinel})
    assert response.status_code==401
    rendered='\n'.join(JsonFormatter().format(record) for record in caplog.records)
    assert sentinel not in rendered and 'synthetic-private@example.com' not in rendered
    assert any(getattr(record,'event',None)=='auth.login.failed' for record in caplog.records)


def test_lifecycle_events(caplog):
    from backend.main import app
    with caplog.at_level(logging.INFO),TestClient(app):pass
    events=[getattr(record,'event',None) for record in caplog.records]
    for name in ('app.starting','config.loaded','database.engine.ready','app.started','app.stopping','app.stopped'):
        assert name in events


def test_operation_r2_import_rejection_is_private_before_any_sql(capsys, caplog):
    from sqlalchemy import create_engine, event as sql_event
    from sqlalchemy.orm import Session
    from backend.core.exceptions import LeadForgeException
    from backend.schemas.execution_principal import ExecutionPrincipal
    from backend.services.lead_import_service import LeadImportService

    marker = "SyntheticR2!"
    candidate = ExecutionPrincipal.for_user(7, 1).model_copy(
        update={"organization_id": {"password": marker}})
    engine = create_engine("sqlite:///:memory:")
    statements = []
    sql_event.listen(engine, "before_cursor_execute", lambda *args: statements.append(True))
    capsys.readouterr()
    caplog.clear()
    try:
        with Session(engine, autoflush=False) as db, caplog.at_level(logging.INFO):
            with warnings.catch_warnings(record=True) as emitted:
                warnings.simplefilter("always")
                with pytest.raises(LeadForgeException) as rejected:
                    LeadImportService(db).confirm(
                        candidate, content=b"", token="", organization_id=candidate.organization_id,
                        user_id=7, session_key="")
            assert not db.new and not db.dirty
    finally:
        engine.dispose()
    error = rejected.value
    assert error.status_code == 400 and error.error_code == "EXECUTION_IDENTITY_INVALID"
    assert str(error) == "Invalid execution identity."
    assert error.__cause__ is None and error.__context__ is None
    assert statements == [] and emitted == []
    output = capsys.readouterr()
    assert marker not in output.out + output.err + caplog.text
    assert marker not in str(error) + repr(error) + "".join(traceback.format_exception(error))
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("import.confirm.")]
    assert [r.event for r in records] == ["import.confirm.started", "import.confirm.failed"]
    assert [r.levelno for r in records] == [logging.INFO, logging.WARNING]
    for record in caplog.records:
        assert marker not in JsonFormatter().format(record)
    for record in records:
        assert not hasattr(record, "organization_id") and not hasattr(record, "user_id")


def test_operation_r2_success_does_not_inspect_arguments_or_result(caplog):
    from backend.core.logger import operation

    class Opaque:
        def __str__(self):
            pytest.fail("Instrumentation rendered an argument/result")

        __repr__ = __str__

        @property
        def summary(self):
            pytest.fail("Instrumentation inspected a result summary")

        @property
        def user(self):
            pytest.fail("Instrumentation inspected a result user")

    value = Opaque()
    calls = []

    @operation("test.r2.success")
    def command(organization_id, *, user_id, lead_id, correlation_id, filename, source):
        calls.append((organization_id, user_id, lead_id, correlation_id, filename, source))
        return value

    token = request_id_context.set("r2-framework-correlation")
    try:
        with caplog.at_level(logging.INFO):
            result = command(value, user_id=value, lead_id=value, correlation_id=value,
                             filename=value, source=value)
    finally:
        request_id_context.reset(token)
    assert result is value and calls == [(value,) * 6]
    assert command.__name__ == "command" and command.__wrapped__.__name__ == "command"
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("test.r2.success.")]
    assert [r.event for r in records] == ["test.r2.success.started", "test.r2.success.completed"]
    assert all(r.levelno == logging.INFO for r in records)
    assert records[-1].duration_ms >= 0
    for record in records:
        data = json.loads(JsonFormatter().format(record))
        assert data["request_id"] == "r2-framework-correlation"
        assert not {"organization_id", "user_id", "lead_id", "total", "ready", "imported",
                    "duplicates", "invalid"} & data.keys()


def test_operation_r2_failure_preserves_exception_without_logging_raw_values(caplog, capsys):
    from backend.core.logger import operation
    marker = "SyntheticR2!"
    error = RuntimeError(marker)

    @operation("test.r2.failure")
    def command(organization_id, user_id, *, lead_id, **kwargs):
        raise error

    capsys.readouterr()
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError) as rejected:
        command(marker, {"password": marker}, lead_id=marker, source=marker, correlation_id=marker)
    assert rejected.value is error
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("test.r2.failure.")]
    assert [r.event for r in records] == ["test.r2.failure.started", "test.r2.failure.failed"]
    failed = records[-1]
    assert failed.levelno == logging.WARNING and failed.exception_type == "RuntimeError"
    assert failed.duration_ms >= 0 and failed.exc_info is None
    for record in records:
        data = json.loads(JsonFormatter().format(record))
        assert marker not in json.dumps(data)
        assert not {"organization_id", "user_id", "lead_id"} & data.keys()
    output = capsys.readouterr()
    assert marker not in output.out + output.err + caplog.text


def test_operation_r2_failure_only_mode_remains_quiet_on_success(caplog):
    from backend.core.logger import operation
    result = object()
    error = ValueError("SyntheticR2!")

    @operation("test.r2.session", success=False)
    def command(fail):
        if fail:
            raise error
        return result

    with caplog.at_level(logging.INFO):
        assert command(False) is result
        assert not [r for r in caplog.records if getattr(r, "event", "").startswith("test.r2.session.")]
        with pytest.raises(ValueError) as rejected:
            command(True)
    assert rejected.value is error
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("test.r2.session.")]
    assert [r.event for r in records] == ["test.r2.session.failed"]
    assert records[0].levelno == logging.WARNING and records[0].exception_type == "ValueError"
    assert "SyntheticR2!" not in JsonFormatter().format(records[0])


def test_operation_r2_valid_import_keeps_lifecycle_and_business_result(client, caplog):
    from sqlalchemy import select
    from backend.database.session import SessionLocal
    from backend.models import Lead, Organization, OrganizationMembership, User
    from backend.schemas.execution_principal import ExecutionPrincipal
    from backend.services.lead_import_service import LeadImportService

    with SessionLocal() as db:
        org = Organization(name="Disposable R2", slug="r2-import")
        user = User(email="r2-import@example.invalid", password_hash="unused-synthetic-hash")
        db.add_all([org, user])
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role="member"))
        db.commit()
        principal = ExecutionPrincipal.for_user(user.id, org.id, correlation_id="r2-import")
        service = LeadImportService(db)
        content = b"company,email,source\nSynthetic,r2-created@example.com,test\n"
        signing_key = "0" * 64  # Disposable test signing material.
        caplog.clear()
        with caplog.at_level(logging.INFO):
            preview = service.preview(content, org.id, user.id, signing_key)
            result = service.confirm(principal, content, preview.token, org.id, user.id, signing_key)
        assert preview.summary.ready == 1 and result.imported == 1
        assert result.total == 1 and result.duplicates == result.invalid == 0
        assert db.scalar(select(Lead.id).where(Lead.organization_id == org.id,
                                             Lead.email == "r2-created@example.com")) is not None
    records = [r for r in caplog.records if getattr(r, "event", "").startswith(("import.preview.", "import.confirm."))]
    assert [r.event for r in records] == ["import.preview.started", "import.preview.completed",
                                       "import.confirm.started", "import.confirm.completed"]
    for record in records:
        data = json.loads(JsonFormatter().format(record))
        assert record.levelno == logging.INFO
        assert not {"organization_id", "user_id", "total", "ready", "imported",
                    "duplicates", "invalid"} & data.keys()
        assert preview.token not in json.dumps(data)
