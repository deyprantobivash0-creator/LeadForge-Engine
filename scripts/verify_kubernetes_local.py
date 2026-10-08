"""Synthetic Kubernetes rehearsal verification, using existing application/recovery gates."""
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.kubernetes_local import (NS,PRIVATE,OUTPUT,MANIFESTS,safety,kubectl,executable)
from scripts.postgres_backup import PgTools,BackupError,backup,restore,sha256
from scripts.verify_backup_recovery import fingerprint,comparable
from scripts.staging_smoke import smoke

class KubernetesPgTools(PgTools):
    """Reuse archive/checksum/fresh-target policy with kubectl's binary transport."""
    def __init__(self,database='leadforge_stage',user='leadforge_stage_admin'):
        self.pod='backup-tools' if user=='leadforge_stage_backup' else 'postgres-0'
        super().__init__(self.pod,database,user,password='mounted-secret')
    def execute(self,tool,*args,connected=True,stdin=None,stdout=None):
        command=[executable('kubectl'),'--context=docker-desktop','-n',NS,'exec','-i',self.pod,'--']
        if connected:
            key='backup' if self.user=='leadforge_stage_backup' else 'admin'
            # Shell contains only a mounted filename; credential never enters argv.
            command += ['sh','-c',f'export PGPASSWORD="$(cat /run/secrets/{key}_password)"; export PGCONNECT_TIMEOUT=5; export PGOPTIONS="-c statement_timeout=120000 -c lock_timeout=10000"; exec "$@"','sh']
        command += [tool]
        if connected:command += ['--host=postgres','--port=5432','--username='+self.user,'--dbname='+self.database,'--no-password']
        command += list(args)
        result=subprocess.run(command,stdin=stdin,stdout=stdout or subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        if result.returncode:raise BackupError('Kubernetes PostgreSQL transport failed; raw driver output withheld')
        return result.stdout

def verify():
    safety()
    kubectl('apply','-f',str(MANIFESTS/'backup-tools.yaml'))
    kubectl('wait','--for=condition=Ready','pod/backup-tools','--timeout=60s',timeout=70)
    original_hash=sha256(ROOT/'leadforge.db')
    evidence=dict(status='RUNNING',scope='Docker Desktop local synthetic rehearsal only')
    tools=KubernetesPgTools()
    version=tools.server_metadata()
    assert version['postgres_version'].split()[0]=='16.15'
    state=json.loads(tools.query("SELECT json_build_object('app_create',has_schema_privilege('leadforge_stage_app','public','CREATE'),'app_alembic_update',has_table_privilege('leadforge_stage_app','alembic_version','UPDATE'),'unsafe_roles',(SELECT count(*) FROM pg_roles WHERE rolname IN ('leadforge_stage_app','leadforge_stage_migrator','leadforge_stage_backup') AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)));"))
    assert not state['app_create'] and not state['app_alembic_update'] and state['unsafe_roles']==0
    evidence['database_roles']=state
    fixture=json.loads((OUTPUT/'fixture.json').read_text())
    context=ssl.create_default_context(cafile=str(PRIVATE/'fullchain.pem'))
    host='staging.leadforge.test'
    forward_log=(OUTPUT/'port-forward.log').open('w')
    forward=subprocess.Popen([executable('kubectl'),'--context=docker-desktop','-n',NS,'port-forward','--address=127.0.0.1','service/local-ingress','58443:8443'],stdout=forward_log,stderr=forward_log)
    resolver=socket.getaddrinfo
    def resolve(name,port,*args,**kw):
        return resolver('127.0.0.1',58443,*args,**kw) if name==host else resolver(name,port,*args,**kw)
    socket.getaddrinfo=resolve
    import urllib.request
    def ready():
        with urllib.request.urlopen('https://'+host+'/ready',context=context,timeout=10) as response:
            assert response.status==200
    def wait_ready():
        for attempt in range(60):
            try:ready();return
            except Exception:time.sleep(1)
        raise RuntimeError('HTTPS readiness did not recover')
    def logs():
        return '\n'.join(kubectl('logs','deployment/'+name).stdout for name in ('backend','frontend','local-ingress'))
    try:
        wait_ready()
        def oversized_check(origin, headers):
            import shutil
            curl=shutil.which('curl.exe') or shutil.which('curl')
            if not curl:raise RuntimeError('curl required for ingress upload boundary check')
            payload=OUTPUT/'oversized-upload.bin'
            payload.write_bytes(b'x'*(2*1024*1024+1))
            request_id='5hl-size-'+uuid4().hex
            response_headers=OUTPUT/'oversized-response-headers.txt'
            result=subprocess.run([curl,'--silent','--show-error','--max-time','20',
                '--connect-to',host+':443:127.0.0.1:58443','--cacert',str(PRIVATE/'fullchain.pem'),
                '--header','X-Request-ID: '+request_id,'--data-binary','@'+str(payload),
                '--dump-header',str(response_headers),'--output','NUL','--write-out','%{http_code}',
                origin+'/api/leads/'],capture_output=True,text=True,timeout=25)
            assert result.returncode==0 and result.stdout=='413'
            assert request_id in response_headers.read_text()
            evidence['oversized_upload_rejected']=True
        evidence['https_smoke']=smoke(host,fixture['fixtures'],(PRIVATE/'qa_password').read_text().strip(),context=context,oversized_check=oversized_check)
        captured=logs()
        for request_id in evidence['https_smoke']['request_ids']:assert request_id in captured
        evidence['structured_logs_request_ids']=True
        (OUTPUT/'runtime-logs.txt').write_text(captured)
        print('PASS HTTPS application/auth/CSRF/tenant/CSV/mock AI/headers and correlation smoke',flush=True)
        baseline=comparable(fingerprint(tools))
        pvc=json.loads(kubectl('get','pvc','data-postgres-0','-o','json').stdout)
        assert pvc['status']['phase']=='Bound'
        pvc_uid=pvc['metadata']['uid'];volume=pvc['spec']['volumeName']
        for name in ('backend','frontend','postgres'):
            selector='app='+name
            before=json.loads(kubectl('get','pods','-l',selector,'-o','json').stdout)['items'][0]['metadata']['uid']
            kubectl('delete','pod','-l',selector,'--wait=true')
            workload='statefulset/postgres' if name=='postgres' else 'deployment/'+name
            kubectl('rollout','status',workload,'--timeout=180s',timeout=190)
            kubectl('wait','--for=condition=Ready','pod','-l',selector,'--timeout=180s',timeout=190)
            after=json.loads(kubectl('get','pods','-l',selector,'-o','json').stdout)['items'][0]['metadata']['uid']
            assert before!=after
            wait_ready()
            assert comparable(fingerprint(tools))==baseline
            evidence[name+'_pod_recreation']=True
            print('PASS '+name+' pod recreation and persistence',flush=True)
        after_pvc=json.loads(kubectl('get','pvc','data-postgres-0','-o','json').stdout)
        assert after_pvc['metadata']['uid']==pvc_uid and after_pvc['spec']['volumeName']==volume
        evidence['pvc_identity_persistence']=True
        for name in ('backend','frontend'):
            kubectl('rollout','restart','deployment/'+name)
            kubectl('rollout','status','deployment/'+name,'--timeout=180s',timeout=190)
        wait_ready();assert comparable(fingerprint(tools))==baseline
        evidence['rolling_restart']=True
        config=json.loads(kubectl('get','configmap','leadforge-config','-o','json').stdout)
        config['data']['VERSION']='5h-l-config-rehearsal'
        config.pop('status',None);config['metadata'].pop('managedFields',None)
        kubectl('apply','-f','-',input=json.dumps(config))
        kubectl('rollout','restart','deployment/backend')
        kubectl('rollout','status','deployment/backend','--timeout=180s',timeout=190)
        wait_ready();assert comparable(fingerprint(tools))==baseline
        assert kubectl('exec','deployment/backend','--','printenv','VERSION').stdout.strip()=='5h-l-config-rehearsal'
        kubectl('apply','-f',str(MANIFESTS/'config.yaml'))
        kubectl('rollout','restart','deployment/backend')
        kubectl('rollout','status','deployment/backend','--timeout=180s',timeout=190)
        wait_ready();evidence['configmap_update_and_revert']=True
        print('PASS rolling restart and safe ConfigMap update/revert',flush=True)
        archive=backup(KubernetesPgTools(user='leadforge_stage_backup'),ROOT/'backups/leadforge-kubernetes-local','production')
        target='leadforge_5hl_restore_'+uuid4().hex[:12]
        tools.query('CREATE DATABASE '+target+" TEMPLATE template0 ENCODING 'UTF8';")
        recovered=KubernetesPgTools(target)
        try:
            restore(recovered,archive,f'postgres-0/{target}')
            assert comparable(fingerprint(recovered))==baseline
            try:restore(recovered,archive,f'postgres-0/{target}')
            except BackupError:pass
            else:raise RuntimeError('Populated restore target was accepted')
        finally:tools.query('DROP DATABASE '+target+' WITH (FORCE);')
        evidence['backup_restore']=dict(status='PASS',size_bytes=archive.stat().st_size,sha256=sha256(archive),populated_target_rejected=True)
        print('PASS Kubernetes backup/recovery using existing archive policy',flush=True)
        # A failed migrator plus missing required head cannot start an app pod.
        fail=json.loads((MANIFESTS/'migrate.yaml').read_text());fail['metadata']['name']='migration-failure-check'
        c=fail['spec']['template']['spec']['containers'][0]
        c['env']=[dict(name='LEADFORGE_STAGE_ROLE',value='invalid')]
        kubectl('apply','-f','-',input=json.dumps(fail))
        kubectl('wait','--for=condition=Failed','job/migration-failure-check','--timeout=60s',timeout=70)
        gated=json.loads((MANIFESTS/'backend.yaml').read_text());gated['metadata']['name']='migration-gated-check'
        gated['spec']['selector']['matchLabels']['app']='migration-gated-check'
        gated['spec']['template']['metadata']['labels']['app']='migration-gated-check'
        gated['spec']['template']['spec']['initContainers'][0]['env'].append(dict(name='LEADFORGE_SCHEMA_HEAD',value='missing-head-for-failure-drill'))
        kubectl('apply','-f','-',input=json.dumps(gated))
        for attempt in range(40):
            pods=json.loads(kubectl('get','pods','-l','app=migration-gated-check','-o','json').stdout)['items']
            if pods:
                states=pods[0]['status'].get('initContainerStatuses',[])
                if states and states[0].get('lastState',{}).get('terminated',{}).get('exitCode')==1:break
            time.sleep(1)
        else:raise RuntimeError('Migration failure startup gate not observed')
        assert not any(c.get('ready') for c in pods[0]['status'].get('containerStatuses',[]))
        assert 'Migration gate closed' in kubectl('logs','deployment/migration-gated-check','-c','schema-gate','--previous').stdout
        evidence['migration_failure_blocks_backend']=True
        kubectl('delete','deployment/migration-gated-check','job/migration-failure-check')
        assert comparable(fingerprint(tools))==baseline
        print('PASS failed migration and schema gate prevent application startup',flush=True)
        services=json.loads(kubectl('get','services','-o','json').stdout)['items']
        assert all(s['spec']['type']=='ClusterIP' and not s['spec'].get('externalIPs') for s in services)
        pods=json.loads(kubectl('get','pods','-o','json').stdout)['items']
        for pod in pods:
            spec=pod['spec'];assert not spec.get('hostNetwork') and not spec.get('hostPID')
            for c in spec['containers']+spec.get('initContainers',[]):
                assert not any(p.get('hostPort') for p in c.get('ports',[]))
                assert c['securityContext']['allowPrivilegeEscalation'] is False
                assert c['securityContext']['readOnlyRootFilesystem'] is True
                assert c['securityContext']['capabilities']['drop']==['ALL']
                assert c['resources']['requests'] and c['resources']['limits']
        evidence['exposure_security_context_audit']=dict(services=[s['metadata']['name'] for s in services],type='ClusterIP',browser_binding='127.0.0.1:58443',nodeport=False,loadbalancer=False)
        assert comparable(fingerprint(tools))==baseline
        evidence['status']='PASS'
    finally:
        if sys.exc_info()[0] is not None:
            evidence['status']='FAILED'
        socket.getaddrinfo=resolver
        forward.terminate();forward.wait(timeout=15);forward_log.close()
        kubectl('delete','pod/backup-tools','--ignore-not-found=true')
        assert sha256(ROOT/'leadforge.db')==original_hash
        evidence['leadforge_db_sha256']=original_hash
        (OUTPUT/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('PASS full local Kubernetes infrastructure/application rehearsal',flush=True)

if __name__=='__main__':
    try:verify()
    except Exception as error:
        import traceback
        frame=traceback.extract_tb(error.__traceback__)[-1]
        print(f'Kubernetes verification failed ({type(error).__name__}, {Path(frame.filename).name}:{frame.lineno}); no completion claimed',file=sys.stderr)
        raise SystemExit(1) from None
