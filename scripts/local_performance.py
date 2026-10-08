"""Bounded measurements through production Nginx; pipe into disposable backend."""
import concurrent.futures
import http.cookiejar
import json
import os
import platform
import ssl
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

assert os.environ.get('LEADFORGE_E2E_DISPOSABLE') == 'true'
assert os.environ.get('AI_PROVIDER') == 'mock'
ORIGIN = 'http://127.0.0.1:8080'
BASE = 'http://frontend:8080'
TLS_CONTEXT = ssl.create_default_context()


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), urllib.request.HTTPSHandler(context=TLS_CONTEXT))

    def request(self, path, data=None, method=None, headers=None):
        headers = {'Host': '127.0.0.1:8080', 'Origin': ORIGIN, 'X-Request-ID': 'e2e-' + uuid4().hex, **(headers or {})}
        if isinstance(data, dict):
            data = json.dumps(data).encode(); headers['Content-Type'] = 'application/json'
        start = time.perf_counter()
        try:
            response = self.opener.open(urllib.request.Request(BASE + path, data=data, method=method, headers=headers), timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        raw = response.read()
        if response.status < 500:
            assert response.headers.get('X-Request-ID') == headers['X-Request-ID']
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            body = raw.decode(errors='replace')
        return response.status, body, (time.perf_counter() - start) * 1000, {k.lower(): v for k, v in response.headers.items()}

    def login(self):
        result = self.request('/api/auth/login', {'email': 'e2e@example.com', 'password': 'local synthetic E2E password'})
        assert result[0] == 200, result[0]
        self.csrf = next(c.value for c in self.jar if c.name == 'leadforge_csrf')
        self.orgs = self.request('/api/organizations')[1]
        self.headers = {'X-Organization-ID': str(self.orgs[0]['id']), 'X-CSRF-Token': self.csrf}
        return result[2]


def summary(samples):
    values = sorted(s[2] for s in samples)
    def percentile(p):
        position = (len(values) - 1) * p
        lower = int(position); upper = min(lower + 1, len(values) - 1)
        return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 2)
    return {'requests': len(values), 'failures': sum(s[0] != 200 for s in samples), 'p50_ms': percentile(.5), 'p95_ms': percentile(.95), 'p99_ms': percentile(.99), 'max_ms': round(max(values), 2)}


def main():
    client = Client(); login_ms = client.login()
    unauthenticated = Client().request('/api/leads/')
    assert unauthenticated[0] == 401
    invalid_org = client.request('/api/leads/', headers={**client.headers, 'X-Organization-ID': '2147483647'})
    assert invalid_org[0] == 403
    leads = client.request('/api/leads/', headers=client.headers)[1]
    lead_id = next(l['id'] for l in leads['items'] if l['email'] == 'fixture-0@example.com')
    cross_tenant = client.request(f'/api/leads/{lead_id}', headers={**client.headers, 'X-Organization-ID': str(client.orgs[1]['id'])})
    assert cross_tenant[0] == 404
    headers = client.request('/api/leads/', headers=client.headers)[3]
    assert headers['cache-control'] == 'no-store' and headers['x-content-type-options'] == 'nosniff'
    static_headers = client.request('/')[3]
    assert "default-src 'self'" in static_headers['content-security-policy']
    endpoints = {'health': '/health', 'readiness': '/ready', 'leads': '/api/leads/', 'detail': f'/api/leads/{lead_id}', 'dashboard': '/api/dashboard/v2/overview', 'reports': '/api/reports/v2/overview?preset=today', 'intelligence': f'/api/leads/{lead_id}/intelligence', 'session': '/api/auth/me'}
    output = {'provider': 'MOCK PROVIDER ONLY', 'environment': {'os': platform.system(), 'python': platform.python_version(), 'logical_cpus': os.cpu_count(), 'target': 'production Nginx http://frontend:8080 with canonical loopback Host', 'database': 'disposable PostgreSQL 16.15', 'workers': 'one Uvicorn process'}, 'baseline': {}, 'concurrency': [], 'imports': []}
    output['security'] = {'unauthenticated': 401, 'invalid_org': 403, 'cross_tenant': 404, 'safe_headers': True}
    for name, path in endpoints.items():
        client.request(path, headers=client.headers)  # warmup excluded
        samples = [client.request(path, headers=client.headers) for _ in range(30)]
        output['baseline'][name] = summary(samples)
        assert all(s[0] == 200 for s in samples)
    print('E2E_PROGRESS=' + json.dumps(output['baseline']), flush=True)
    # Freeze only synthetic auth cookies; separate opener per worker prevents cookie-jar races.
    cookie = '; '.join(c.name + '=' + c.value for c in client.jar)
    read_headers = {**client.headers, 'Cookie': cookie}
    for workers in [1, 5, 10, 25, 50]:
        for name in ['leads', 'dashboard', 'reports']:
            def request(_):
                return Client().request(endpoints[name], headers=read_headers)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                samples = list(pool.map(request, range(max(50, workers * 2))))
            metric = summary(samples); metric.update(endpoint=name, concurrency=workers)
            output['concurrency'].append(metric)
            assert metric['failures'] == 0 and metric['max_ms'] < 10000, metric
            if name == 'leads':
                assert all(all(l['email'] != 'fixture-1@example.com' for l in s[1]['items']) for s in samples)
            if name == 'dashboard':
                assert len({json.dumps(s[1]['pipeline'], sort_keys=True) for s in samples}) == 1
            if name == 'reports':
                assert len({json.dumps(s[1]['summary'], sort_keys=True) for s in samples}) == 1
        time.sleep(.25)
    # Authentic Argon2 work: five additional sessions stay below the existing 10/min budget.
    logins, logouts = [login_ms], []
    for _ in range(4):
        auth = Client(); logins.append(auth.login())
        logout = auth.request('/api/auth/logout', method='POST', headers={'X-CSRF-Token': auth.csrf})
        assert logout[0] == 200; logouts.append(logout[2])
    output['auth'] = {name: summary([(200, None, ms, {}) for ms in samples]) for name, samples in [('login', logins), ('logout', logouts)]}
    ai = client.request(f'/api/leads/{lead_id}/process', method='POST', headers=client.headers)
    assert ai[0] == 200 and ai[1]['processing_status'] == 'completed'
    persisted = client.request(f'/api/leads/{lead_id}/intelligence', headers=client.headers)
    assert persisted[1]['analysis']['id'] == ai[1]['analysis']['id']
    output['mock_ai'] = {'request_and_commit_ms': ai[2], 'subsequent_persisted_read_ms': persisted[2], 'total_observed_ms': ai[2] + persisted[2], 'separate_commit_timing': 'not instrumented'}
    def duplicate(_):
        return Client().request('/api/leads/', {'company': 'Race Synthetic', 'email': 'race@example.com', 'source': 'e2e'}, headers=read_headers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        race = list(pool.map(duplicate, range(10)))
    output['duplicate_race'] = {str(status): sum(s[0] == status for s in race) for status in set(s[0] for s in race)}
    print('E2E_RACE=' + json.dumps(output['duplicate_race']), flush=True)
    assert output['duplicate_race'] == {'200': 1, '409': 9}, output['duplicate_race']
    csv_headers = {**client.headers, 'Content-Type': 'text/csv'}
    for rows in [10, 100, 500, 1000]:
        content = ('company,email,source\n' + ''.join(f'Perf {i},perf-{rows}-{i}@example.com,e2e\n' for i in range(rows))).encode()
        before = client.request('/api/leads/', headers=client.headers)[1]['total']
        preview = client.request('/api/imports/leads/preview', content, headers=csv_headers)
        assert preview[0] == 200 and preview[1]['summary']['ready'] == rows
        assert client.request('/api/leads/', headers=client.headers)[1]['total'] == before
        confirm = client.request('/api/imports/leads/confirm', content, headers={**csv_headers, 'X-Import-Preview-Token': preview[1]['token']})
        assert confirm[0] == 200 and confirm[1]['imported'] == rows
        duplicate_preview = client.request('/api/imports/leads/preview', content, headers=csv_headers)
        assert duplicate_preview[1]['summary']['duplicates'] == rows
        output['imports'].append({'rows': rows, 'preview_ms': preview[2], 'confirm_ms': confirm[2], 'imported': rows, 'duplicate_preview_ms': duplicate_preview[2], 'duplicates': rows})
    boundary = []
    for label, content, expected in [('empty', b'company,email,source\n', 422), ('nul', b'company,email,source\na,\x00,b', 422), ('malformed', b'company,email,source\n"unterminated', 422), ('oversized', b'x' * (1048576 + 1), 413), ('1001-rows', ('company,email,source\n' + 'A,a@example.com,e2e\n' * 1001).encode(), 422)]:
        result = client.request('/api/imports/leads/preview', content, headers=csv_headers)
        assert result[0] == expected, (label, result[0])
        boundary.append({'case': label, 'status': result[0], 'ms': result[2]})
    output['boundaries'] = boundary
    large = client.request('/api/leads/?page_size=100', headers=client.headers)
    page2 = client.request('/api/leads/?page_size=100&page=2', headers=client.headers)
    assert len(large[1]['items']) == 100 and not ({l['id'] for l in large[1]['items']} & {l['id'] for l in page2[1]['items']})
    output['large_list'] = {'total': large[1]['total'], 'page_size': 100, 'duration_ms': large[2], 'disjoint_pages': True}
    output['large_baseline'] = {name: summary([client.request(endpoints[name], headers=client.headers) for _ in range(30)]) for name in ['leads', 'dashboard', 'reports']}
    assert all(m['failures'] == 0 for m in output['large_baseline'].values())
    # Current protection: ten accepted login attempts/minute per shared proxy peer, then 429.
    rate = [client.request('/api/auth/login', {'email': 'missing@example.com', 'password': 'invalid'}) for _ in range(11)]
    assert any(s[0] == 429 and s[3].get('retry-after') for s in rate)
    output['rate_limit'] = {'statuses': [s[0] for s in rate], 'shared_proxy_peer': True}
    print('E2E_RESULT=' + json.dumps(output))


def probe(mode):
    client = Client(); client.login()
    samples = []
    paths = ['/api/auth/me'] if mode == '--session-probe' else ['/health', '/ready', '/api/leads/']
    for _ in range(25):
        for path in paths:
            result = client.request(path, headers=client.headers)
            assert result[0] in [200, 401, 500, 503]
            if result[0] >= 500:
                assert 'postgresql' not in json.dumps(result[1]).lower()
                assert 'password' not in json.dumps(result[1]).lower()
            samples.append({'path': path, 'status': result[0], 'ms': result[2]})
        time.sleep(.2)
    print('E2E_PROBE=' + json.dumps(samples))


if __name__ == '__main__':
    probe(sys.argv[1]) if len(sys.argv) > 1 else main()
