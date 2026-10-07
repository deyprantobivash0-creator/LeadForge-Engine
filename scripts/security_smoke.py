"""Focused security smoke for the named local development/mock runtime only."""
import json
import subprocess
import time
from observability_smoke import request, logs


def main():
    info = json.loads(subprocess.check_output(['docker', 'inspect', 'leadforge-runtime-local-backend-1']))[0]
    env = dict(item.split('=', 1) for item in info['Config']['Env'])
    assert env['ENVIRONMENT'] == 'development' and env['AI_PROVIDER'] == 'mock'
    for path in ['/', '/leads', '/imports', '/reports', '/health', '/api/auth/me', '/api/settings/overview']:
        status, headers, _ = request(path)
        assert status in {200, 401}
        assert headers.get_all('X-Content-Type-Options') == ['nosniff']
        assert headers.get_all('X-Frame-Options') == ['DENY']
        assert headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        assert 'camera=()' in headers['Permissions-Policy']
        assert "script-src 'self'" in headers['Content-Security-Policy']
        assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
        assert 'Strict-Transport-Security' not in headers
        if path.startswith('/api/'):
            assert headers.get_all('Cache-Control') == ['no-store']
    assert request('/health', headers={'Host': 'attacker.invalid', 'X-Forwarded-Host': 'localhost'})[0] == 400
    assert request('/api/auth/login', headers={'Content-Type': 'application/json'}, data=b'x'*(2*1024*1024+1))[0] == 413
    print('PASS actual proxy headers, CSP, cache, Host and oversized request policy', flush=True)
    payload = json.dumps({'email': 'security-absent@example.com', 'password': 'synthetic-security-password'}).encode()
    rejected = False
    for i in range(11):
        status, headers, body = request('/api/auth/login', headers={'Content-Type': 'application/json',
            'X-Forwarded-For': f'198.51.100.{i}', 'Forwarded': f'for=198.51.100.{i}'}, data=payload)
        assert status in {401, 429} and b'synthetic-security-password' not in body
        if status == 429:
            rejected = True
            delay = int(headers['Retry-After'])
            assert 1 <= delay <= 60
            break
    assert rejected
    print(f'PASS proxy login abuse throttled despite spoofed headers; recovery wait={delay}s', flush=True)
    time.sleep(delay + 0.2)
    assert request('/api/auth/login', headers={'Content-Type': 'application/json'}, data=payload)[0] == 401
    for component in ['backend', 'frontend']:
        rendered = json.dumps(logs(f'leadforge-runtime-local-{component}-1'))
        assert 'synthetic-security-password' not in rendered
    print('PASS actual limiter expiry/recovery and password privacy', flush=True)


if __name__ == '__main__':
    main()
