"""Local runtime-only structured logging, correlation and synthetic privacy audit."""
import json
from http.cookies import SimpleCookie
import subprocess
import urllib.error
import urllib.request
import uuid

BASE='http://127.0.0.1:8080'


def request(path, *, headers=None, data=None):
    query=urllib.request.Request(BASE+path,headers=headers or {},data=data)
    try:
        response=urllib.request.urlopen(query,timeout=15)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        return response.status, response.headers, response.read()


def logs(container):
    result=subprocess.run(['docker','logs',container],capture_output=True,check=True)
    lines=(result.stdout+result.stderr).decode().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main():
    info=json.loads(subprocess.run(['docker','inspect','leadforge-runtime-local-backend-1'],capture_output=True,check=True).stdout)[0]
    environment=dict(value.split('=',1) for value in info['Config']['Env'])
    assert environment['ENVIRONMENT']=='development' and environment['AI_PROVIDER']=='mock'
    sentinel='synthetic-5d-'+uuid.uuid4().hex
    identity='synthetic-5d-correlation-'+uuid.uuid4().hex
    auth_identity='synthetic-5d-auth-'+uuid.uuid4().hex
    status,headers,body=request('/health?private='+sentinel,headers={'X-Request-ID':identity,'Cookie':'unrelated='+sentinel,'Authorization':'Bearer '+sentinel})
    assert status==200 and headers.get_all('X-Request-ID')==[identity]
    assert sentinel.encode() not in body
    status,headers,body=request('/api/auth/login?private='+sentinel,headers={'X-Request-ID':auth_identity,'Content-Type':'application/json','X-CSRF-Token':sentinel},data=json.dumps({'email':'synthetic-private-'+sentinel+'@example.com','password':sentinel}).encode())
    assert status==401 and sentinel.encode() not in body
    for incoming in ('invalid id','x'*65):
        status,headers,_=request('/health',headers={'X-Request-ID':incoming})
        assert status==200 and headers['X-Request-ID']!=incoming and len(headers['X-Request-ID'])==32
    status,cookie_headers,_=request('/api/auth/login',headers={'Content-Type':'application/json'},
        data=json.dumps({'email':'runtime-smoke@example.com','password':'container fixture password'}).encode())
    assert status==200
    cookies=SimpleCookie()
    for value in cookie_headers.get_all('Set-Cookie'):cookies.load(value)
    session=cookies['leadforge_session'].value;csrf=cookies['leadforge_csrf'].value
    authenticated={'Cookie':f'leadforge_session={session}; leadforge_csrf={csrf}'}
    status,_,body=request('/api/organizations',headers=authenticated)
    assert status==200
    organization=next(row['id'] for row in json.loads(body) if row['name']=='Runtime Synthetic 1')
    private_lead='synthetic-lead-'+sentinel+'@example.com'
    content=f'company,email,source\nSynthetic {sentinel},{private_lead},fixture\n'.encode()
    status,_,_=request('/api/imports/leads/preview',headers={**authenticated,'Content-Type':'text/csv',
        'X-CSRF-Token':csrf,'X-Organization-ID':str(organization)},data=content)
    assert status==200
    status,_,_=request('/api/auth/logout',headers={**authenticated,'X-CSRF-Token':csrf},data=b'')
    assert status==200
    backend=logs('leadforge-runtime-local-backend-1')
    frontend=logs('leadforge-runtime-local-frontend-1')
    migration=logs('leadforge-runtime-local-migrate-1')
    for component in (backend,frontend,migration):
        rendered=json.dumps(component)
        for private in (sentinel,session,csrf,private_lead,'container fixture password'):
            assert private not in rendered
    matches=[row for row in frontend if row.get('request_id')==identity]
    # Healthy probes are DEBUG in backend; a non-probe auth request verifies both layers.
    backend_matches=[row for row in backend if row.get('event')=='http.request.completed' and row.get('request_id')==auth_identity]
    assert len(backend_matches)==1 and backend_matches[0]['status_code']==401
    assert any(row.get('request_id')==auth_identity for row in frontend)
    assert matches and matches[-1]['status_code']==200
    assert any(row.get('event')=='auth.login.failed' for row in backend)
    assert any(row.get('event')=='migration.completed' for row in migration)
    print('PASS structured backend/frontend/migration JSON, correlation and single backend completion event')
    print('PASS actual synthetic session/CSRF, password/query/cookie/authorization/email/CSV payload absent from emitted logs and error/health responses')


if __name__=='__main__':main()
