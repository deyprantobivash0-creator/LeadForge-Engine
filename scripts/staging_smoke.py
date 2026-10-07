"""External trusted-HTTPS synthetic staging checks. Does not provision or seed data."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.request
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.staging import hostname


def smoke(host, fixture, password, *, context=None):
    origin = "https://" + hostname(host)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(jar))
    responses = []
    request_ids = []

    def request(path, expected=200, data=None, headers=None, method=None, parsed=True):
        headers = {"Origin": origin, "X-Request-ID": "5h-" + uuid4().hex, **(headers or {})}
        request_ids.append(headers["X-Request-ID"])
        if isinstance(data, dict):
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        req = urllib.request.Request(origin + path, data=data, headers=headers, method=method)
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            if response.status != expected or password.encode() in body:
                raise ValueError("Staging HTTP/status/privacy assertion failed")
            if response.headers.get("X-Request-ID") != headers["X-Request-ID"]:
                raise ValueError("Request correlation failed")
            if response.headers.get("X-Robots-Tag") != "noindex, nofollow, noarchive":
                raise ValueError("Indexing policy missing")
            responses.append(body)
            return (json.loads(body) if body and parsed else body), response.headers

    for path in ("/health", "/ready"):
        request(path)
    for path in ("/", "/leads", "/imports", "/ai", "/ai/1", "/reports", "/settings"):
        body, headers = request(path, parsed=False)
        assert b'<div id="root">' in body and "text/html" in headers["Content-Type"]
        assert "Content-Security-Policy" in headers and headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Strict-Transport-Security"] == "max-age=86400"
        assert "Referrer-Policy" in headers and "Permissions-Policy" in headers
        assert "nginx/" not in headers.get("Server", "")
    robots, _ = request("/robots.txt", parsed=False)
    assert b"Disallow: /" in robots
    for path in ("/docs", "/redoc", "/openapi.json"):
        request(path, expected=404, parsed=False)
    request("/api/auth/me", expected=401)
    request("/api/auth/login", expected=403, data={"email": fixture[0]["email"], "password": password}, headers={"Origin": "https://malicious.invalid"})
    request("/api/auth/login", expected=401, data={"email": fixture[0]["email"], "password": "synthetic-invalid-password"})
    _, headers = request("/api/auth/login", data={"email": fixture[0]["email"], "password": password})
    cookies = headers.get_all("Set-Cookie", [])
    assert all("Secure" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie for cookie in cookies)
    assert any("leadforge_session=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert all(cookie.secure for cookie in jar)
    raw_session = next(cookie.value for cookie in jar if cookie.name == "leadforge_session")
    csrf = next(cookie.value for cookie in jar if cookie.name == "leadforge_csrf")
    assert headers["Access-Control-Allow-Origin"] == origin
    request("/api/auth/me")
    orgs, _ = request("/api/organizations")
    assert {org["id"] for org in orgs} == {fixture[0]["organization_id"]}
    tenant = {"X-Organization-ID": str(fixture[0]["organization_id"])}
    foreign = fixture[1]["lead_ids"][0]
    for path in (f"/api/leads/{foreign}", f"/api/leads/{foreign}/intelligence"):
        request(path, expected=404, headers=tenant)
    request("/api/reports/v2/export.csv", expected=403, headers={"X-Organization-ID": str(fixture[1]["organization_id"])}, parsed=False)
    for path in ("/api/dashboard/v2/overview", "/api/leads/", "/api/reports/v2/overview", "/api/settings/overview"):
        request(path, headers=tenant)
    before, _ = request("/api/leads/", headers=tenant)
    dashboard, _ = request("/api/dashboard/v2/overview", headers=tenant)
    assert dashboard["pipeline"]["total_leads"] == before["total"]
    assert len({row["lead_id"] for row in dashboard["top_opportunities"]}) == len(dashboard["top_opportunities"])
    for lead_id in fixture[0]["lead_ids"]:
        history, _ = request(f"/api/leads/{lead_id}/analyses", headers=tenant)
        intelligence, _ = request(f"/api/leads/{lead_id}/intelligence", headers=tenant)
        assert history["total"] >= 2
        latest = max(history["items"], key=lambda row: (row["created_at"], row["id"]))
        assert intelligence["analysis"]["id"] == latest["id"]
    report, _ = request("/api/reports/v2/overview", headers=tenant)
    assert report["summary"]["analysis_events"] >= 4 and report["summary"]["unique_analyzed_leads"] >= 2
    csv = f"company,email,source\nSYNTHETIC HTTPS import,staging-import-{uuid4().hex[:8]}@example.com,staging-synthetic\n".encode()
    csv_headers = {**tenant, "Content-Type": "text/csv"}
    request("/api/imports/leads/preview", expected=403, data=csv, headers=csv_headers)
    csv_headers["X-CSRF-Token"] = csrf
    preview, _ = request("/api/imports/leads/preview", data=csv, headers=csv_headers)
    after, _ = request("/api/leads/", headers=tenant)
    assert before == after and preview["summary"]["ready"] == 1
    imported, _ = request("/api/imports/leads/confirm", data=csv, headers={**csv_headers, "X-Import-Preview-Token": preview["token"]})
    assert imported["imported"] == 1
    duplicate, _ = request("/api/imports/leads/preview", data=csv, headers=csv_headers)
    assert duplicate["summary"]["duplicates"] == 1
    lead = fixture[0]["lead_ids"][0]
    request(f"/api/leads/{lead}/process", method="POST", data={}, headers={**tenant, "X-CSRF-Token": csrf})
    request(f"/api/leads/{lead}/intelligence", headers=tenant)
    exported, _ = request("/api/reports/v2/export.csv", headers=tenant, parsed=False)
    assert b"staging-beta" not in exported
    request("/api/auth/logout", method="POST", expected=403)
    request("/api/auth/logout", method="POST", headers={"X-CSRF-Token": csrf})
    request("/api/auth/me", expected=401, headers={"Cookie": "leadforge_session=" + raw_session})
    request("/api/leads/", expected=413, method="POST", data=b"x" * (2 * 1024 * 1024 + 1),
            headers={**tenant, "X-CSRF-Token": csrf}, parsed=False)
    for _ in range(12):
        req = urllib.request.Request(origin + "/api/auth/login", data=json.dumps({"email": fixture[0]["email"], "password": "synthetic-invalid-password"}).encode(),
            headers={"Origin": origin, "Content-Type": "application/json"})
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if response.status == 429:
                assert int(response.headers["Retry-After"]) > 0
                break
            assert response.status == 401
    else:
        raise ValueError("Shared login budget was not enforced")
    for body in responses:
        assert raw_session.encode() not in body and csrf.encode() not in body
    return {"status": "PASS", "transport": "trusted HTTPS" if context is None else "LOCAL TEST CA; not public staging TLS",
            "request_ids": request_ids, "checks": "health, SPA, indexing, headers, cookies, auth, workspace, tenant, Dashboard, Leads, CSV preview/import/export, mock process, Intelligence, Reports, Settings, logout/revocation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        fixture = json.loads(args.fixture_manifest.read_text())
        if not fixture.get("synthetic"):
            raise ValueError("Synthetic fixture required")
        print(json.dumps(smoke(args.hostname, fixture["fixtures"], args.password_file.read_text().strip())))
    except Exception:
        print("Staging smoke failed; check trusted HTTPS, private fixture credentials and server logs", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
