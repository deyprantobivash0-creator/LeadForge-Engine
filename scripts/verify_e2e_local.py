"""Repeatable Step 5J-L rehearsal. Owns only a uniquely named disposable project."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRESERVED = ['leadforge.db', 'docs/STEP_5F_VERIFICATION.md', 'docs/STEP_5H_B_VERIFICATION.md', 'package.json', 'package-lock.json']


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() if (ROOT / name).exists() else None for name in PRESERVED}


def memory_bytes(value):
    number, unit = re.fullmatch(r'([0-9.]+)([A-Za-z]+)', value.strip()).groups()
    factors = {'B': 1, 'kB': 1000, 'MB': 1000 ** 2, 'GB': 1000 ** 3, 'KiB': 1024, 'MiB': 1024 ** 2, 'GiB': 1024 ** 3}
    return float(number) * factors[unit]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', default='.staging-artifacts/5j-l')
    args = parser.parse_args()
    evidence = (ROOT / args.evidence).resolve()
    if not evidence.is_relative_to(ROOT / '.staging-artifacts'):
        raise ValueError('Evidence must remain under ignored .staging-artifacts')
    evidence.mkdir(parents=True, exist_ok=True)
    docker = shutil.which('docker')
    if not docker:
        raise RuntimeError('Docker/Compose required on PATH')
    before = hashes()
    project = 'leadforge-e2e-' + uuid4().hex[:12]
    env = os.environ.copy()
    for key in ['LEADFORGE_ENV_FILE', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'LANGCHAIN_API_KEY']:
        env.pop(key, None)
    env['LEADFORGE_RUNTIME_DB_PASSWORD'] = uuid4().hex + uuid4().hex
    env['LEADFORGE_CI_IMAGE_NAMESPACE'] = project
    override = evidence / 'compose.json'
    override.write_text(json.dumps({'services': {
        'backend': {'environment': {'LEADFORGE_E2E_DISPOSABLE': 'true'}},
        'migrate': {'environment': {'LEADFORGE_E2E_DISPOSABLE': 'true'}},
    }}), encoding='utf-8')
    compose = [docker, 'compose', '--env-file', str(ROOT / 'deploy/compose.env'), '-p', project, '-f', str(ROOT / 'compose.runtime.yml'), '-f', str(ROOT / 'deploy/compose.ci.yml'), '-f', str(override)]
    drivers = set()

    def run(command, *, stdin=None, timeout=600, capture=True):
        result = subprocess.run(command, input=stdin, env=env, cwd=ROOT, capture_output=capture, text=True, timeout=timeout)
        if result.returncode:
            # Never echo command/env with random DB password. Logs use application redaction.
            if capture:
                print(result.stdout[-6000:]); print(result.stderr[-6000:])
            raise RuntimeError(f'Local command failed with exit {result.returncode}')
        return result.stdout if capture else ''

    def helper(name, *options):
        if name == 'local_performance.py':
            driver = project + '-driver-' + uuid4().hex[:6]
            drivers.add(driver)
            # Keep the completed driver until finally: a sampler may still hold
            # its ID when traffic ends. Removing it mid-sample races Docker stats.
            return run([docker, 'run', '-i', '--name', driver,
                        '--label', 'leadforge.e2e.project=' + project,
                        '--network', project + '_runtime', '--cpus', '2', '--memory', '256m',
                        '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                        '-e', 'AI_PROVIDER=mock', '-e', 'LEADFORGE_E2E_DISPOSABLE=true',
                        '--entrypoint', 'python', project + ':backend', '-B', '-', *options],
                       stdin=(ROOT / 'scripts' / name).read_text(encoding='utf-8'))
        return run([*compose, 'exec', '-T', 'backend', 'python', '-B', '-', *options], stdin=(ROOT / 'scripts' / name).read_text(encoding='utf-8'))

    def http(path):
        code = "import urllib.request,urllib.error,json\ntry:\n r=urllib.request.urlopen(urllib.request.Request('http://frontend:8080" + path + "',headers={'Host':'127.0.0.1:8080'}),timeout=8)\nexcept urllib.error.HTTPError as e:\n r=e\nprint(json.dumps({'status':r.status,'body':r.read().decode()}))"
        return json.loads(run([*compose, 'exec', '-T', 'backend', 'python', '-B', '-c', code]))

    def wait_ready():
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if http('/ready')['status'] == 200:
                    return
            except (RuntimeError, ValueError):
                pass
            time.sleep(1)
        raise AssertionError('Runtime did not recover readiness')

    def browser():
        frontend = run([*compose, 'ps', '-q', 'frontend']).strip()
        run([docker, 'run', '--rm', '--network', 'container:' + frontend, '--ipc', 'host',
             '--mount', f'type=bind,source={evidence},target=/evidence', project + ':browser'], capture=False)

    report = {'status': 'FAIL', 'project': project, 'provider': 'mock', 'preserved_before': before, 'resilience': {}}
    report['docker'] = json.loads(run([docker, 'info', '--format', '{"engine":"{{.ServerVersion}}","logical_cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}']))
    started = time.monotonic()
    try:
        print('Building production backend/frontend/PostgreSQL and isolated Playwright tool', flush=True)
        run([*compose, 'build'], capture=False)
        run([docker, 'build', '-f', 'deploy/e2e.Dockerfile', '-t', project + ':browser', '.'], capture=False)
        run([*compose, 'up', '-d', '--wait', '--wait-timeout', '120'], capture=False)
        fixture = helper('e2e_fixture.py', 'seed')
        report['fixture'] = json.loads(fixture.strip().splitlines()[-1])
        print('Running browser journeys against production Nginx', flush=True)
        browser()
        report['browser'] = 'PASS'
        failed = helper('e2e_fixture.py', 'failed-analysis')
        report['failed_analysis'] = json.loads(failed.strip().splitlines()[-1])
        print('Waiting for the existing shared login budget before bounded measurements', flush=True)
        time.sleep(61)
        report['connections_before'] = json.loads(helper('e2e_fixture.py', 'connections').strip().splitlines()[-1])
        print('Measuring representative requests, concurrency 1/5/10/25/50 and CSV 10/100/500/1000', flush=True)
        # Resource sampling is independent of request traffic. Keep samples and bounded measurements local.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(helper, 'local_performance.py')
            stats = []
            sustained_cpu = 0
            while not future.done():
                ids = run([*compose, 'ps', '-q']).split()
                ids += run([docker, 'ps', '-q', '--filter', 'label=leadforge.e2e.project=' + project]).split()
                sample = run([docker, 'stats', '--no-stream', '--format', '{{json .}}', *ids])
                stats.append(sample)
                (evidence / 'resources.json').write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')
                resources = [json.loads(line) for line in sample.splitlines() if line.strip()]
                sustained_cpu = sustained_cpu + 1 if sum(float(r['CPUPerc'].rstrip('%')) for r in resources) > 800 else 0
                if sum(memory_bytes(r['MemUsage'].split('/')[0]) for r in resources) > report['docker']['memory_bytes'] * .5 or sustained_cpu >= 2:
                    run([*compose, 'stop', 'backend'])
                    raise RuntimeError('Stopped disposable traffic: local resource safety budget exceeded')
                time.sleep(2)
            output = future.result()
        payload = next(line[len('E2E_RESULT='):] for line in output.splitlines() if line.startswith('E2E_RESULT='))
        performance = json.loads(payload)
        (evidence / 'performance.json').write_text(json.dumps(performance, indent=2) + '\n', encoding='utf-8')
        (evidence / 'resources.json').write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')
        report['connections_after'] = json.loads(helper('e2e_fixture.py', 'connections').strip().splitlines()[-1])
        assert not any(row['state'].startswith('idle in transaction') for row in report['connections_after'])
        assert sum(row['count'] for row in report['connections_after']) <= 16
        report['query_review'] = json.loads(helper('e2e_fixture.py', 'query-review').strip().splitlines()[-1])
        print('Testing isolated database outage, backend restart and frontend restart', flush=True)
        time.sleep(61)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            traffic = pool.submit(helper, 'local_performance.py', '--outage-probe')
            time.sleep(1)
            run([*compose, 'stop', '-t', '10', 'postgres'])
            outage = {'ready': http('/ready'), 'health': http('/health')}
            assert outage['ready']['status'] == 503 and outage['health']['status'] == 200
            assert 'unavailable' in outage['ready']['body']
            assert env['LEADFORGE_RUNTIME_DB_PASSWORD'] not in json.dumps(outage)
            time.sleep(1)  # Keep the fault observable to the bounded traffic probe.
            run([*compose, 'start', 'postgres']); wait_ready()
            samples = json.loads(next(line[len('E2E_PROBE='):] for line in traffic.result().splitlines() if line.startswith('E2E_PROBE=')))
        assert any(s['status'] >= 500 for s in samples)
        report['resilience']['database'] = {**outage, 'traffic': samples, 'recovered': True}
        # A separate lightweight probe container continues through each restart.
        probe = "import urllib.request,time,json\nr=[]\nfor i in range(30):\n try:\n  q=urllib.request.urlopen(urllib.request.Request('http://frontend:8080/ready',headers={'Host':'127.0.0.1:8080'}),timeout=2);r.append(q.status)\n except Exception:\n  r.append('unavailable')\n time.sleep(.2)\nprint(json.dumps(r))"
        network = project + '_runtime'
        for service in ['backend', 'frontend']:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                traffic = pool.submit(run, [docker, 'run', '--rm', '--network', network, '--entrypoint', 'python', project + ':backend', '-c', probe])
                time.sleep(.5)
                run([*compose, 'restart', service]); wait_ready()
                statuses = json.loads(traffic.result().strip())
            report['resilience'][service] = {'statuses': statuses, 'recovered': http('/ready')['status'] == 200}
        print('Repeating browser auth/recovery smoke after restart and synthetic expiration', flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            sessions = pool.submit(helper, 'local_performance.py', '--session-probe')
            time.sleep(1); helper('e2e_fixture.py', 'expire')
            samples = json.loads(next(line[len('E2E_PROBE='):] for line in sessions.result().splitlines() if line.startswith('E2E_PROBE=')))
        assert samples[0]['status'] == 200 and any(s['status'] == 401 for s in samples)
        report['expired_session'] = samples
        report['connections_recovered'] = json.loads(helper('e2e_fixture.py', 'connections').strip().splitlines()[-1])
        assert not any(row['state'].startswith('idle in transaction') for row in report['connections_recovered'])
        assert sum(row['count'] for row in report['connections_recovered']) <= 16
        # Browser suite is rerunnable against fresh fixtures; recovery only reruns auth, avoiding mutations.
        frontend = run([*compose, 'ps', '-q', 'frontend']).strip()
        time.sleep(61)
        helper('e2e_fixture.py', 'failed-analysis')
        run([docker, 'run', '--rm', '--network', 'container:' + frontend, '--ipc', 'host', '-e', 'E2E_RECOVERY=1', '-e', 'E2E_REPORT=/evidence/browser-recovery.json', '--mount', f'type=bind,source={evidence},target=/evidence', project + ':browser', 'npx', '--no-install', 'playwright', 'test', 'auth.spec.js', 'recovery.spec.js'], capture=False)
        logs = run([*compose, 'logs', '--no-color', 'backend'])
        assert env['LEADFORGE_RUNTIME_DB_PASSWORD'] not in logs
        assert 'local synthetic E2E password' not in logs and 'browser-import@example.com' not in logs
        assert '"request_id":"e2e-' in logs and '"request_id":"e2e-browser-' in logs and '"provider_name":"mock"' in logs
        (evidence / 'runtime.log').write_text(logs, encoding='utf-8')
        report['log_correlation_privacy'] = True
        report['status'] = 'PASS'
    finally:
        try:
            logs = run([*compose, 'logs', '--no-color', 'backend'])
            assert env['LEADFORGE_RUNTIME_DB_PASSWORD'] not in logs
            (evidence / 'runtime.log').write_text(logs, encoding='utf-8')
        finally:
            for driver in drivers:
                subprocess.run([docker, 'rm', '-f', driver], env=env, capture_output=True, timeout=30)
            run([*compose, 'down', '--volumes', '--remove-orphans'], capture=False)
        report['preserved_after'] = hashes()
        report['cleanup'] = 'unique project containers/networks/volume removed'
        report['duration_seconds'] = round(time.monotonic() - started, 2)
        (evidence / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        assert before == report['preserved_after'], 'Preexisting file changed'
    print('PASS Step 5J local browser/performance/resilience rehearsal', flush=True)


if __name__ == '__main__':
    main()
