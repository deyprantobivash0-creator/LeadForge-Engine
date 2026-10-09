"""Isolated LOCAL Render transport rehearsal; never contacts a cloud provider."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_staging import certificate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    output = (ROOT / args.evidence).resolve()
    if not output.is_relative_to(ROOT / ".staging-artifacts"):
        raise ValueError("Ignored local evidence path required")
    output.mkdir(parents=True, exist_ok=False)
    project = "leadforge-render-local-" + uuid4().hex[:10]
    network = project + "-private"
    owned = []
    env = os.environ.copy()
    for key in ("LEADFORGE_ENV_FILE", "GEMINI_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "HUBSPOT_ACCESS_TOKEN"):
        env.pop(key, None)
    passwords = {key: secrets.token_urlsafe(36) for key in ("admin", "owner", "migrator", "app", "backup", "qa")}
    before = hashlib.sha256((ROOT / "leadforge.db").read_bytes()).hexdigest()
    report = {"scope":"LOCAL transport simulation, not Render acceptance/deployment", "project":project, "provider":"mock", "status":"FAIL"}

    def run(command, *, stdin=None, check=True, timeout=600, extra=None):
        r = subprocess.run(command, input=stdin, env={**env, **(extra or {})}, cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        if any(value in r.stdout + r.stderr for value in passwords.values()):
            raise RuntimeError("Synthetic secret leaked")
        if check and r.returncode:
            print((r.stdout + r.stderr)[-3000:])
            raise RuntimeError("Local Render verification subprocess failed")
        return r

    def launch(name, image, options, command=(), extra=None):
        owned.append(name)
        return run(["docker", "run", "-d", "--name", name, "--label", "leadforge.render.local="+project,
                    "--network", network, *options, image, *command], extra=extra)

    common = {"ENVIRONMENT":"production", "AI_PROVIDER":"mock", "LEADFORGE_STAGING":"true",
              "CORS_ORIGINS":"https://frontend-fixture.onrender.com", "SESSION_COOKIE_SECURE":"true",
              "LEADFORGE_RENDER_DB_TLS":"internal", "PORT":"10000", "RENDER_EXTERNAL_HOSTNAME":"backend-fixture.onrender.com"}
    def driver(code, role="owner", extra=None, check=True):
        username = "local_fixture_admin" if role == "admin" else "leadforge_stage_" + role
        variables = {**common, "DATABASE_URL":"postgresql://"+username+":"+passwords[role]+"@"+project+"-pg/leadforge_stage", **(extra or {})}
        return run(["docker", "run", "--rm", "-i", "--network", network, "--entrypoint", "python",
                    "--mount",f"type=bind,source={ROOT/'scripts'},target=/app/scripts,readonly",
                    *[arg for key in variables for arg in ("-e",key)], project+":backend", "-B", "-"], stdin=code, extra=variables, check=check)

    try:
        for component, dockerfile in (("backend","Dockerfile"),("frontend","frontend/Dockerfile")):
            result = run(["docker","build","-t",project+":"+component,"-f",dockerfile,"."])
            (output/(component+"-build.log")).write_text(result.stdout+result.stderr,encoding="utf-8")
        run(["docker","network","create","--internal",network])
        for key, host in (("backend","backend-fixture.onrender.com"),("frontend","frontend-fixture.onrender.com"),("pg",project+"-pg")):
            directory=output/key;directory.mkdir();certificate(directory,host)
        # PostgreSQL copies its own synthetic TLS key to a private runtime path.
        launch(project+"-pg", "postgres:16.15", ["-e","POSTGRES_USER=local_fixture_admin","-e","POSTGRES_DB=leadforge_stage","-e","POSTGRES_PASSWORD",
            "--mount",f"type=bind,source={output/'pg'},target=/fixture,readonly","--entrypoint","sh"],
            ["-ec","cp /fixture/privkey.pem /var/lib/postgresql/pg-key; cp /fixture/fullchain.pem /var/lib/postgresql/pg-cert; chown postgres:postgres /var/lib/postgresql/pg-key /var/lib/postgresql/pg-cert; chmod 600 /var/lib/postgresql/pg-key; exec docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/var/lib/postgresql/pg-cert -c ssl_key_file=/var/lib/postgresql/pg-key"],
            {"POSTGRES_PASSWORD":passwords["admin"]})
        connect="from deploy.render.runtime import configure; configure()\nimport psycopg,os\nfrom sqlalchemy.engine import make_url\nu=make_url(os.environ['DATABASE_URL']); c=psycopg.connect(host=u.host,dbname=u.database,user=u.username,password=u.password,connect_timeout=5,sslmode='require')\n"
        deadline=time.monotonic()+90
        while driver(connect+"c.close()", role="admin", check=False).returncode != 0:
            if time.monotonic()>deadline:raise RuntimeError("Private PostgreSQL readiness timeout")
            time.sleep(2)
        driver(connect+"from psycopg import sql\nc.execute(sql.SQL('CREATE ROLE leadforge_stage_owner LOGIN NOSUPERUSER NOCREATEDB CREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(os.environ['LOCAL_OWNER_PASSWORD'])))\nc.execute('ALTER DATABASE leadforge_stage OWNER TO leadforge_stage_owner'); c.commit(); c.close()", role="admin", extra={"LOCAL_OWNER_PASSWORD":passwords["owner"]})
        variables={"LEADFORGE_RENDER_"+key.upper()+"_PASSWORD":passwords[key] for key in ("migrator","app","backup")}
        driver(connect+"from deploy.render.provision import provision\nprovision(c,{key:os.environ['LEADFORGE_RENDER_'+key.upper()+'_PASSWORD'] for key in ('migrator','app','backup')}); c.commit(); c.close()",extra=variables)
        driver("from deploy.render.runtime import configure; configure()\nimport subprocess,sys\nsubprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)","migrator")
        driver(connect+"from deploy.render.provision import provision\nprovision(c,{},finalize=True); c.commit(); c.close()")
        assertions="""assert c.execute("SELECT has_schema_privilege('leadforge_stage_app','public','CREATE'),has_table_privilege('leadforge_stage_app','alembic_version','UPDATE')").fetchone()==(False,False)
assert c.execute("SELECT bool_or(rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls) FROM pg_roles WHERE rolname IN ('leadforge_stage_app','leadforge_stage_migrator','leadforge_stage_backup')").fetchone()==(False,)
assert c.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone()==(True,)
print('PASS role separation, TLS and base-to-head migration')
c.close()
"""
        driver(connect+assertions)
        seeded=driver("from deploy.render.runtime import configure;configure()\nfrom deploy.staging.seed import seed\nimport os\nseed(os.environ['LEADFORGE_RENDER_QA_PASSWORD'])","app",{"LEADFORGE_RENDER_QA_PASSWORD":passwords["qa"]})
        variables={**common,"DATABASE_URL":"postgresql://leadforge_stage_app:"+passwords["app"]+"@"+project+"-pg/leadforge_stage"}
        # Exercise image default CMD, the path that previously bypassed the adapter.
        launch(project+"-backend",project+":backend",["--network-alias","backend",*[arg for key in variables for arg in ("-e",key)]],extra=variables)
        frontend_vars={"LEADFORGE_RENDER":"true","PORT":"10000","RENDER_EXTERNAL_HOSTNAME":"frontend-fixture.onrender.com","LEADFORGE_RENDER_BACKEND_ORIGIN":"https://backend-fixture.onrender.com"}
        launch(project+"-frontend",project+":frontend",["--network-alias","frontend",*[arg for key in frontend_vars for arg in ("-e",key)],
            "--mount",f"type=bind,source={output/'backend'/'fullchain.pem'},target=/etc/ssl/certs/ca-certificates.crt,readonly"],extra=frontend_vars)
        edge=output/'edge.conf'
        edge.write_text('pid /tmp/edge.pid; events {} http { client_max_body_size 3m; server_tokens off; access_log off; error_log /dev/stderr crit; client_body_temp_path /tmp/client; proxy_temp_path /tmp/proxy; '
            'server { listen 443 ssl; server_name backend-fixture.onrender.com; ssl_certificate /fixture/backend/fullchain.pem; ssl_certificate_key /fixture/backend/privkey.pem; location / { proxy_set_header Host backend-fixture.onrender.com; proxy_pass http://backend:10000; } } '
            'server { listen 443 ssl; server_name frontend-fixture.onrender.com; ssl_certificate /fixture/frontend/fullchain.pem; ssl_certificate_key /fixture/frontend/privkey.pem; location / { proxy_set_header Host frontend-fixture.onrender.com; proxy_pass http://frontend:10000; } } }',encoding='utf-8')
        launch(project+"-edge",project+":frontend",["--network-alias","backend-fixture.onrender.com","--network-alias","frontend-fixture.onrender.com","--entrypoint","nginx",
            "--mount",f"type=bind,source={output},target=/fixture,readonly"],["-c","/fixture/edge.conf","-g","daemon off;"])
        ca=(output/'frontend'/'fullchain.pem').read_text(encoding='utf-8')
        probe="import ssl,urllib.request,time\nc=ssl.create_default_context(cadata="+repr(ca)+")\n"
        probe+="for i in range(45):\n try:\n  r=urllib.request.urlopen('https://frontend-fixture.onrender.com/ready',context=c,timeout=8);assert r.status==200;break\n except Exception:\n  time.sleep(2)\nelse:raise AssertionError('Proxy readiness failed')\n"
        driver(probe)
        driver("""import urllib.request,urllib.error
for host,expected in [('backend-fixture.onrender.com',200),('unknown.example.com',400),('something-else.onrender.com',400)]:
    request=urllib.request.Request('http://backend:10000/ready',headers={'Host':host,'X-Forwarded-Host':'backend-fixture.onrender.com'})
    try:
        response=urllib.request.urlopen(request,timeout=8)
    except urllib.error.HTTPError as error:
        response=error
    assert response.status==expected
print('PASS originless exact Render Host readiness and unknown/sibling/forwarded-host rejection')
""")
        # Uvicorn diagnostics are deliberately redacted by the structured logger.
        run(['docker','exec',project+'-backend','python','-c',
            "from pathlib import Path; args=Path('/proc/1/cmdline').read_bytes().split(b'\\0'); "
            "assert args[args.index(b'--host')+1]==b'0.0.0.0'; "
            "assert args[args.index(b'--port')+1]==b'10000'; print('PASS actual PID 1 binds 0.0.0.0:10000')"])
        # Reuse canonical HTTPS tenant/CSRF/mock/CSV smoke, with an explicit local trust file.
        fixture=json.loads(seeded.stdout.strip().splitlines()[-1])["fixtures"]
        code="import ssl,json,os\nfrom scripts.staging_smoke import smoke\ncontext=ssl.create_default_context(cadata="+repr(ca)+")\nprint(json.dumps(smoke('frontend-fixture.onrender.com',"+repr(fixture)+",os.environ['LEADFORGE_RENDER_QA_PASSWORD'],context=context)))\n"
        result=driver(code,"app",{"LEADFORGE_RENDER_QA_PASSWORD":passwords["qa"]});(output/'https-smoke.log').write_text(result.stdout,encoding='utf-8')
        # Verify the HTTPS trust boundary rejects the wrong issuer (no insecure fallback).
        launch(project+"-bad-ca",project+":frontend",[*[arg for key in frontend_vars for arg in ("-e",key)],
            "--mount",f"type=bind,source={output/'frontend'/'fullchain.pem'},target=/etc/ssl/certs/ca-certificates.crt,readonly"],extra=frontend_vars)
        negative="import urllib.request,urllib.error,time\nfor i in range(20):\n try:\n  urllib.request.urlopen(urllib.request.Request('http://"+project+"-bad-ca:10000/ready',headers={'Host':'frontend-fixture.onrender.com'}),timeout=8)\n except urllib.error.HTTPError as e:\n  assert e.code==502;break\n except OSError:\n  time.sleep(1)\nelse:raise AssertionError('TLS rejection failed')\n"
        driver(negative)
        for unsafe in ("http://backend-fixture.onrender.com", "https://user:synthetic@backend-fixture.onrender.com", "https://backend-fixture.onrender.com/path"):
            variables={**frontend_vars,"LEADFORGE_RENDER_BACKEND_ORIGIN":unsafe}
            result=run(["docker","run","--rm","--network=none",*[arg for key in variables for arg in ("-e",key)],project+":frontend"],extra=variables,check=False)
            assert result.returncode!=0 and "Render Nginx configuration rejected" in result.stderr and unsafe not in result.stderr
        driver("import ssl,urllib.request,urllib.error\nc=ssl.create_default_context(cadata="+repr(ca)+")\ntry:\n r=urllib.request.urlopen(urllib.request.Request('https://frontend-fixture.onrender.com/api/auth/me',headers={'X-Request-ID':'render-proxy-correlation'}),context=c,timeout=10)\nexcept urllib.error.HTTPError as e:\n r=e\nassert r.headers['X-Request-ID']=='render-proxy-correlation'\n")
        logs=''
        for name in owned:
            if name.endswith(('-frontend','-backend')):
                captured=run(['docker','logs',name]).stdout
                assert 'render-proxy-correlation' in captured
                logs+=captured
        assert all(value not in logs for value in passwords.values())
        assert '"request_id":' in logs
        report.update(status="PASS",roles_tls_migration="PASS",https_proxy_smoke="PASS",runtime_port=10000,log_privacy="PASS",request_id_correlation="PASS",tls_negative="PASS",unsafe_upstream_negative="PASS")
        print('PASS local Render ports, verified HTTPS proxy, opaque-cookie auth/tenant/CSRF/mock/CSV, roles/TLS/migration and log privacy')
    finally:
        for name in reversed(owned):
            result=run(["docker","logs",name],check=False)
            (output/(name+".log")).write_text(result.stdout+result.stderr,encoding="utf-8")
            run(["docker","rm","-f","-v",name],check=False)
        run(["docker","network","rm",network],check=False)
        assert hashlib.sha256((ROOT/'leadforge.db').read_bytes()).hexdigest()==before
        report['database_preserved']=True
        (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == "__main__":
    main()
