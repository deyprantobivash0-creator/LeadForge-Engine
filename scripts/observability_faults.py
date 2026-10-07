"""Reversible fault exercises for the explicitly named local synthetic runtime only."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from observability_smoke import request, logs

ROOT=Path(__file__).resolve().parents[1]
BASE=['docker','compose','--env-file','deploy/compose.env','-f','compose.runtime.yml']
BACKEND='leadforge-runtime-local-backend-1'
POSTGRES='leadforge-runtime-local-postgres-1'


def run(*command,check=True):
    return subprocess.run(command,cwd=ROOT,capture_output=True,check=check)


def info(container):return json.loads(run('docker','inspect',container).stdout)[0]


def wait_ready():
    for _ in range(50):
        try:
            if request('/ready')[0]==200:return
        except Exception:pass
        time.sleep(.5)
    raise AssertionError('runtime did not recover readiness')


def main():
    environment=dict(value.split('=',1) for value in info(BACKEND)['Config']['Env'])
    assert environment['ENVIRONMENT']=='development' and environment['AI_PROVIDER']=='mock'
    assert '@postgres:5432/leadforge_dev' in environment['DATABASE_URL']
    assert os.environ.get('LEADFORGE_RUNTIME_DB_PASSWORD')
    try:
        run('docker','stop',POSTGRES)
        assert request('/health')[0]==200
        status,headers,body=request('/ready',headers={'X-Request-ID':'synthetic-5d-outage'})
        assert status==503 and json.loads(body)['database']=='unavailable'
        assert any(row.get('event')=='readiness.failed' and row.get('reason')=='database_unavailable' and row.get('request_id')=='synthetic-5d-outage' for row in logs(BACKEND))
        print('PASS DB outage: liveness200/readiness503, correlated database_unavailable event')
    finally:
        run('docker','start',POSTGRES)
    wait_ready();print('PASS DB recovery: readiness200, no data/state repair')
    run('docker','restart',BACKEND);wait_ready()
    names=[row.get('event') for row in logs(BACKEND)]
    assert 'app.stopping' in names and 'app.stopped' in names and names.count('app.started')>=2
    print('PASS graceful restart: stopping/stopped/started lifecycle events')
    started=datetime.now(timezone.utc).isoformat()
    # Signal the process, rather than Docker's explicit manual-stop API.
    run('docker','exec',BACKEND,'python','-c','import os, signal; os.kill(1, signal.SIGTERM)')
    time.sleep(1)
    wait_ready()
    assert info(BACKEND)['RestartCount']>=1
    ending=datetime.now(timezone.utc).isoformat()
    events=run('docker','events','--since',started,'--until',ending,'--filter','container='+BACKEND,'--format','{{json .}}').stdout.decode().splitlines()
    assert any(json.loads(line).get('Action')=='die' for line in events)
    assert not info(BACKEND)['State']['OOMKilled']
    print('PASS controlled process SIGTERM: Docker die/start metadata, automatic restart, lifecycle logs, readiness recovery')
    sentinel='synthetic-5d-'+uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='leadforge-5d-migration-') as directory:
        override=Path(directory)/'failure.yml'
        override.write_text('services:\n  migrate:\n    environment:\n      DATABASE_URL: postgresql+psycopg://leadforge_dev:'+sentinel+'@postgres:5432/nonexistent_synthetic_5d\n  backend:\n    environment:\n      DATABASE_URL: postgresql+psycopg://leadforge_dev:'+sentinel+'@postgres:5432/nonexistent_synthetic_5d\n',encoding='utf-8')
        try:
            run(*BASE,'down')
            result=run(*BASE,'-f',str(override),'up','-d','--wait',check=False)
            assert result.returncode!=0
            migration=info('leadforge-runtime-local-migrate-1')
            assert migration['State']['ExitCode']!=0
            for container in (BACKEND,'leadforge-runtime-local-frontend-1'):
                assert not info(container)['State']['Running']
            output=run('docker','logs','leadforge-runtime-local-migrate-1')
            combined=output.stdout+output.stderr
            assert sentinel.encode() not in combined
            structured=[json.loads(line) for line in combined.decode().splitlines() if line.startswith('{')]
            assert any(row.get('event')=='migration.failed' and row.get('reason')=='database_or_schema_failure' for row in structured)
            assert b'DATABASE_URL migration operation failed' in combined
            print('PASS migration failure: nonzero exit, backend/frontend gated, safe category and no secret')
        finally:
            run(*BASE,'down')
            run(*BASE,'up','-d','--wait')
    wait_ready()
    for container in (BACKEND,'leadforge-runtime-local-frontend-1',POSTGRES):assert info(container)['RestartCount']==0
    print('PASS restored standard runtime healthy, restart counts reset by normal recreation, volume preserved')


if __name__=='__main__':main()
