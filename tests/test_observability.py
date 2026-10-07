"""Operational semantics, correlation and synthetic privacy checks."""
import asyncio
import json
import logging
import uuid
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
