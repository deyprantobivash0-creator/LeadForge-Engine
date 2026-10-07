"""Pipe into the LOCAL backend container; exercises the actual Nginx/API boundary.

Creates only explicitly named synthetic fixtures in the separate runtime volume.
Never runs automatically at startup and never targets the 5A/SQLite databases.
"""

import argparse
import http.cookiejar
import json
import os
import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.engine import make_url

from backend.core.config import settings, secret_value
from backend.core.passwords import hash_password, verify_password
from backend.database.session import SessionLocal
from backend.models import Lead, Organization, OrganizationMembership, User


ORIGIN = "http://127.0.0.1:8080"
EMAIL = "runtime-smoke@example.com"
PASSWORD = "container fixture password"  # Synthetic local fixture only.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-persistence", action="store_true")
    args = parser.parse_args()
    url = make_url(secret_value(settings.DATABASE_URL))
    assert (settings.ENVIRONMENT == "development" and settings.AI_PROVIDER == "mock"
            and url.host == "postgres" and url.database == "leadforge_dev"
            and os.environ.get("LEADFORGE_RUNTIME_LOCAL") == "true"), "Local runtime only"

    with SessionLocal() as db:
        orgs = [db.scalar(select(Organization).where(Organization.slug == slug))
                for slug in ("runtime-smoke-alpha", "runtime-smoke-beta")]
        user = db.scalar(select(User).where(User.email == EMAIL))
        if args.check_persistence:
            assert user and all(orgs)
            assert db.scalar(select(Lead.id).where(
                Lead.organization_id == orgs[0].id, Lead.email == "runtime-import@example.com"
            )) is not None
            print("PASS: synthetic account, memberships and imported Lead survived down/up")
            return
        if user is None:
            user = User(email=EMAIL, password_hash=hash_password(PASSWORD))
            db.add(user)
        else:
            assert verify_password(PASSWORD, user.password_hash), "Unexpected fixture account"
        for index, org in enumerate(orgs):
            if org is None:
                org = Organization(name=f"Runtime Synthetic {index + 1}",
                                   slug=("runtime-smoke-alpha", "runtime-smoke-beta")[index])
                db.add(org)
                orgs[index] = org
        db.flush()
        for org in orgs:
            if db.scalar(select(OrganizationMembership.id).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == org.id,
            )) is None:
                db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role="owner"))
        db.commit()
        ids = [org.id for org in orgs]

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path, expected=200, data=None, headers=None, method=None, json_body=True):
        # Connect by Docker DNS while preserving the public browser authority.
        headers = {"Origin": ORIGIN, "Host": "127.0.0.1:8080", **(headers or {})}
        if isinstance(data, dict):
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        req = urllib.request.Request("http://frontend:8080" + path, data=data,
                                     headers=headers, method=method)
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        assert response.status == expected, (path, response.status, expected)
        body = response.read()
        return (json.loads(body) if body and json_body else body), response.headers

    request("/ready")
    request("/health")
    for path in ("/", "/leads", "/imports", "/ai", "/ai/1", "/reports", "/settings"):
        body, headers = request(path, json_body=False)
        assert b'<div id="root">' in body and "text/html" in headers["Content-Type"]
    request("/api/auth/me", expected=401)
    request("/api/auth/login", expected=403, data={"email": EMAIL, "password": PASSWORD},
            headers={"Origin": "http://untrusted.invalid"})
    _, headers = request("/api/auth/login", data={"email": EMAIL, "password": PASSWORD})
    cookies = " ".join(headers.get_all("Set-Cookie", []))
    assert "HttpOnly" in cookies and "SameSite=lax" in cookies and "Path=/" in cookies
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert headers["Access-Control-Allow-Credentials"] == "true"
    csrf = next(cookie.value for cookie in jar if cookie.name == "leadforge_csrf")
    assert not any(cookie.secure for cookie in jar)  # Explicit local development HTTP.
    assert request("/api/auth/me")[0]["email"] == EMAIL
    workspaces, _ = request("/api/organizations")
    assert {org["id"] for org in workspaces} == set(ids)
    request("/api/leads/", expected=400)
    request("/api/leads/", expected=403, headers={"X-Organization-ID": "2147483647"})
    tenant = {"X-Organization-ID": str(ids[0])}
    for path in ("/api/dashboard/v2/overview", "/api/leads/", "/api/reports/v2/overview",
                 "/api/settings/overview"):
        request(path, headers=tenant)
    csv = b"company,email,source\nRuntime Synthetic,runtime-import@example.com,container-smoke\n"
    csv_headers = {**tenant, "Content-Type": "text/csv"}
    request("/api/imports/leads/preview", expected=403, data=csv, headers=csv_headers)
    csv_headers["X-CSRF-Token"] = csrf
    with SessionLocal() as db:
        before = db.scalar(select(Lead.id).where(
            Lead.organization_id == ids[0], Lead.email == "runtime-import@example.com"
        ))
    preview, _ = request("/api/imports/leads/preview", data=csv, headers=csv_headers)
    with SessionLocal() as db:
        assert db.scalar(select(Lead.id).where(
            Lead.organization_id == ids[0], Lead.email == "runtime-import@example.com"
        )) == before, "Preview must not mutate Leads"
    result, _ = request("/api/imports/leads/confirm", data=csv,
                        headers={**csv_headers, "X-Import-Preview-Token": preview["token"]})
    assert result["imported"] == (0 if before else 1)
    with SessionLocal() as db:
        lead_id = db.scalar(select(Lead.id).where(
            Lead.organization_id == ids[0], Lead.email == "runtime-import@example.com"
        ))
    assert lead_id
    request(f"/api/leads/{lead_id}/intelligence", headers=tenant)
    request(f"/api/leads/{lead_id}/intelligence", expected=404,
            headers={"X-Organization-ID": str(ids[1])})
    request("/api/reports/v2/export.csv", headers=tenant, json_body=False)
    request("/api/auth/logout", expected=403, method="POST")
    request("/api/auth/logout", method="POST", headers={"X-CSRF-Token": csrf})
    request("/api/auth/me", expected=401)
    print("PASS: SPA, same-origin proxy, auth/session/CSRF, workspaces, tenant isolation,")
    print("      Dashboard, Leads, import preview/confirm, intelligence, Reports/CSV, Settings")


if __name__ == "__main__":
    main()
