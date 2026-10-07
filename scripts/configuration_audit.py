"""Read-only, redacted Step 5C audit. Never reads private dotenv or customer DBs."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which('git')


def run(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, check=True)
    return result.stdout


def main():
    if not GIT:
        raise SystemExit('Git is required on PATH for the configuration audit')
    parser = argparse.ArgumentParser()
    parser.add_argument('--sentinel-file', type=Path, required=True)
    args = parser.parse_args()
    sentinel = args.sentinel_file.read_bytes().strip()
    assert sentinel.startswith(b'synthetic-5c-')
    patterns = [rb'AIza[0-9A-Za-z_-]{35}', rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}', rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    findings = set()
    paths = run(GIT, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
    scanned = 0
    for name in filter(None, paths):
        path = ROOT / name
        if (not path.is_file() or path.stat().st_size > 2_000_000 or path.name == '.env'
                or (path.name.startswith('.env.') and path.name != '.env.example')
                or path.suffix in {'.db', '.sqlite', '.sqlite3'}):
            continue
        data = path.read_bytes(); scanned += 1
        assert sentinel not in data, f'sentinel in repository file: {name}'
        if any(re.search(pattern, data) for pattern in patterns):
            findings.add(('working-tree', name))
    historical = 0
    for line in run(GIT, 'rev-list', '--objects', '--all').decode().splitlines():
        oid, _, name = line.partition(' ')
        if not name or run(GIT, 'cat-file', '-t', oid).strip() != b'blob':
            continue
        # Historic tracked content only; no unrelated host files are inspected.
        data = run(GIT, 'cat-file', 'blob', oid); historical += 1
        if any(re.search(pattern, data) for pattern in patterns):
            findings.add(('history', name))
    print(json.dumps({'repository_files_scanned': scanned, 'historical_blobs_scanned': historical,
                      'credential_pattern_findings': sorted(findings)}))
    assert not findings, 'Potential real credential requires review/rotation; values intentionally withheld'
    for image in ('leadforge-backend:5b-local', 'leadforge-frontend:5b-local'):
        assert sentinel not in run('docker', 'image', 'inspect', image)
        assert sentinel not in run('docker', 'history', '--no-trunc', image)
        container = run('docker', 'create', image).decode().strip()
        try:
            with tempfile.TemporaryDirectory(prefix='leadforge-5c-image-') as temporary:
                archive = Path(temporary) / 'image.tar'
                run('docker', 'export', '-o', str(archive), container)
                count = 0
                with tarfile.open(archive) as tar:
                    for member in tar:
                        if not member.isfile():
                            continue
                        data = tar.extractfile(member).read(); count += 1
                        assert sentinel not in data, f'sentinel in image {image}: {member.name}'
                        if member.name.startswith('usr/share/nginx/html/'):
                            for key in (b'GEMINI_API_KEY', b'DEEPSEEK_API_KEY', b'HUBSPOT_ACCESS_TOKEN', b'DATABASE_URL'):
                                assert key not in data, f'backend secret key in public bundle: {key.decode()}'
                        assert not (member.name == 'app/.env' or member.name.startswith('app/.env.'))
                print(f'PASS image filesystem/history/config + public assets: {image}; files={count}')
        finally:
            run('docker', 'rm', container)
    for container in ('leadforge-runtime-local-backend-1', 'leadforge-runtime-local-migrate-1', 'leadforge-runtime-local-frontend-1'):
        logs = subprocess.run(['docker', 'logs', container], capture_output=True, check=True)
        assert sentinel not in logs.stdout + logs.stderr
        inspect = json.loads(run('docker', 'inspect', container))[0]
        environment = dict(item.split('=', 1) for item in inspect['Config']['Env'])
        if 'backend' in container or 'migrate' in container:
            assert environment['AI_PROVIDER'] == 'mock'
            assert environment.get('HUBSPOT_ACCESS_TOKEN', '').encode() in {b'', sentinel}
        assert inspect['HostConfig']['ReadonlyRootfs']
        assert inspect['Config']['User'].split(':')[0] in {'10001', '101'}
        assert inspect['RestartCount'] == 0
        assert not any(mount['Type'] == 'bind' for mount in inspect['Mounts'])
        print(f'PASS runtime log/hardening: {container}')
    migration = json.loads(run('docker', 'inspect', 'leadforge-runtime-local-migrate-1'))[0]
    backend = json.loads(run('docker', 'inspect', 'leadforge-runtime-local-backend-1'))[0]
    values = lambda item: dict(value.split('=', 1) for value in item['Config']['Env'])
    assert values(migration)['DATABASE_URL'] == values(backend)['DATABASE_URL']
    assert migration['State']['ExitCode'] == 0
    for endpoint in ('health', 'ready'):
        with urllib.request.urlopen('http://127.0.0.1:8080/'+endpoint) as response:
            data = response.read(); assert sentinel not in data
            assert b'DATABASE_URL' not in data and b'password' not in data
            print(f'PASS {endpoint}: {response.status}')
    print('PASS externally injected sentinel absent from repo/docs, images/assets, image metadata, normal logs and health; runtime admin inspection intentionally retains it')


if __name__ == '__main__':
    main()
