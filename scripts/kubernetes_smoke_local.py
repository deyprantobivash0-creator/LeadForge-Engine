"""Read-only focused regression for the retained Docker Desktop rehearsal."""
import json
from scripts.kubernetes_local import safety, kubectl


def main():
    safety()
    pods = json.loads(kubectl('get', 'pods', '-o', 'json').stdout)['items']
    for app in ['backend', 'frontend', 'local-ingress', 'postgres']:
        selected = [p for p in pods if p['metadata'].get('labels', {}).get('app') == app]
        assert selected and all(any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])) for p in selected)
    jobs = json.loads(kubectl('get', 'jobs', '-o', 'json').stdout)['items']
    assert all(next(j for j in jobs if j['metadata']['name'] == name)['status'].get('succeeded') == 1 for name in ['provision', 'migrate', 'seed'])
    pvc = json.loads(kubectl('get', 'pvc', 'data-postgres-0', '-o', 'json').stdout)
    assert pvc['status']['phase'] == 'Bound'
    config = json.loads(kubectl('get', 'configmap', 'leadforge-config', '-o', 'json').stdout)
    assert config['data']['AI_PROVIDER'] == 'mock'
    kubectl('exec', 'deployment/backend', '--', 'python', '/kubernetes/check_schema.py')
    code = """import urllib.request,json
for url in ['http://127.0.0.1:8000/ready','http://frontend:8080/frontend-health','http://frontend:8080/leads']:
    request=urllib.request.Request(url,headers={'Host':'staging.leadforge.test'})
    response=urllib.request.urlopen(request,timeout=10)
    assert response.status==200
    if url.endswith('/leads'):
        assert b'<div id="root">' in response.read()
print('PASS readiness, frontend health and production SPA route')
"""
    kubectl('exec', 'deployment/backend', '--', 'python', '-c', code)
    print(json.dumps({'status': 'PASS', 'provider': 'mock', 'pvc_uid': pvc['metadata']['uid'], 'volume': pvc['spec']['volumeName'], 'checks': 'four workloads Ready, jobs succeeded, retained Bound PVC, required Alembic head, backend readiness, frontend health and SPA route'}))


if __name__ == '__main__':
    main()
