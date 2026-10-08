"""Docker Desktop-only local rehearsal operations; never selects another context."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NS = 'leadforge-local'
MANIFESTS = ROOT / 'deploy/kubernetes'
PRIVATE = ROOT / 'secrets/leadforge-kubernetes-local'
OUTPUT = ROOT / '.staging-artifacts/5h-l'

def executable(name):
    found = shutil.which(name)
    if found:
        return found
    for directory in (Path.home() / 'AppData/Local/Programs/DockerDesktop/resources/bin', Path('C:/Program Files/Docker/Docker/resources/bin')):
        path = Path(directory) / (name + '.exe')
        if path.is_file():
            return str(path)
    raise RuntimeError(f'{name} executable unavailable; supply PATH')

def run(args, *, input=None, timeout=180, check=True):
    result = subprocess.run(args, input=input, capture_output=True, text=True,
                            cwd=ROOT, timeout=timeout)
    values = [p.read_text().strip() for p in PRIVATE.glob('*_password')]
    if any(value in result.stdout + result.stderr for value in values):
        raise RuntimeError('Credential appeared in captured output; output withheld')
    if check and result.returncode:
        # Never print raw runtime exceptions or API Secret objects.
        raise RuntimeError(f'Operation failed: {Path(args[0]).name}; exit {result.returncode}')
    return result

def kubectl(*args, **kwargs):
    return run([executable('kubectl'), '--context=docker-desktop', '-n', NS, *args], **kwargs)

def safety():
    if run([executable('kubectl'), 'config', 'current-context']).stdout.strip() != 'docker-desktop':
        raise RuntimeError('STOP: current context is not docker-desktop')
    info = run([executable('kubectl'), '--context=docker-desktop', 'cluster-info']).stdout
    if 'https://127.0.0.1:' not in info:
        raise RuntimeError('STOP: local control-plane endpoint not verified')
    nodes = json.loads(run([executable('kubectl'), '--context=docker-desktop', 'get', 'nodes', '-o', 'json']).stdout)
    if not nodes['items'] or any(not any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes['items']):
        raise RuntimeError('STOP: local nodes not Ready')
    print('PASS docker-desktop safety gate; local endpoint and Ready nodes', flush=True)

def ensure_secret(secret):
    import base64
    existing = kubectl('get', 'secret', secret['metadata']['name'], '-o', 'json', check=False)
    if existing.returncode == 0:
        data = json.loads(existing.stdout)['data']
        expected = secret.get('data') or {k:base64.b64encode(v.encode()).decode() for k,v in secret['stringData'].items()}
        if data != expected:
            raise RuntimeError('Existing Kubernetes Secret differs; coordinate rotation explicitly')
        return
    kubectl('create', '-f', '-', input=json.dumps(secret))


def job(name):
    kubectl('apply','-f',str(MANIFESTS/(name+'.yaml')))
    kubectl('wait','--for=condition=complete','job/'+name,'--timeout=180s',timeout=190)
    print('PASS '+name+' Job', flush=True)

def deploy():
    from scripts.staging import prepare
    from scripts.verify_staging import certificate
    safety()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prepare('staging.leadforge.test', PRIVATE)
    if not (PRIVATE/'fullchain.pem').exists():
        certificate(PRIVATE, 'staging.leadforge.test')
    kubectl('apply','-f',str(MANIFESTS/'namespace.yaml'))
    # API receives JSON on stdin; no values enter arguments, source or stdout.
    secret = dict(apiVersion='v1',kind='Secret',metadata=dict(name='leadforge-credentials',namespace=NS),type='Opaque',stringData={p.name:p.read_text().strip() for p in PRIVATE.glob('*_password')})
    ensure_secret(secret)
    import base64
    tls = dict(apiVersion='v1',kind='Secret',metadata=dict(name='leadforge-local-tls',namespace=NS),type='kubernetes.io/tls',data={k:base64.b64encode((PRIVATE/v).read_bytes()).decode() for k,v in [('tls.crt','fullchain.pem'),('tls.key','privkey.pem')]})
    ensure_secret(tls)
    docker=executable('docker')
    # Docker Desktop uses a kind node with a separate containerd image store.
    node='desktop-control-plane'
    inspect=json.loads(run([docker,'inspect',node]).stdout)[0]
    if inspect['Config']['Image'] != 'kindest/node:v1.36.1':
        raise RuntimeError('Unknown node image; refusing image import')
    images=['leadforge-backend:5h-l-local','leadforge-frontend:5h-l-local','leadforge-postgres:5h-l-local','leadforge-ingress:5h-l-local']
    archive=OUTPUT/'images.tar'
    run([docker,'save','-o',str(archive.relative_to(ROOT)),*images],timeout=300)
    run([docker,'cp',str(archive.relative_to(ROOT)),node+':/root/leadforge-5h-l-images.tar'],timeout=180)
    run([docker,'exec',node,'ctr','-n','k8s.io','images','import','--platform','linux/amd64','/root/leadforge-5h-l-images.tar'],timeout=300)
    print('PASS local image import; no registry publication',flush=True)
    kubectl('apply','-k',str(MANIFESTS))
    kubectl('rollout','status','statefulset/postgres','--timeout=180s',timeout=190)
    job('provision');job('migrate')
    for name in ('backend','frontend'):
        kubectl('apply','-f',str(MANIFESTS/(name+'.yaml')))
        kubectl('rollout','status','deployment/'+name,'--timeout=180s',timeout=190)
    kubectl('rollout','status','deployment/local-ingress','--timeout=180s',timeout=190)
    job('seed')
    seeded=kubectl('logs','job/seed').stdout
    (OUTPUT/'fixture.json').write_text(json.dumps(json.loads(seeded.splitlines()[-1]),indent=2)+'\n')
    print('PASS deployments, PVC, migration and synthetic seed',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['safety','deploy'])
    args=parser.parse_args()
    try:
        {'safety':safety,'deploy':deploy}[args.action]()
    except Exception as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Rehearsal operation failed; inspect private local evidence',file=sys.stderr)
        raise SystemExit(1) from None
