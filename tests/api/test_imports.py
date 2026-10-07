from backend.database.session import SessionLocal
from backend.models.lead import Lead
from backend.models.lead_analysis import LeadAnalysis
from backend.services.lead_import_service import ImportValidationError, parse_csv


def _headers(workspace, user="a", org="a"):
    client = workspace["clients"][user]
    return {
        "X-Organization-ID": str(workspace["ids"]["organizations"][org]),
        "X-CSRF-Token": client.cookies[workspace["csrf_cookie"]],
        "Content-Type": "text/csv",
    }


def _post(workspace, path, csv, user="a", org="a", token=None):
    headers = _headers(workspace, user, org)
    if token:
        headers["X-Import-Preview-Token"] = token
    return workspace["clients"][user].post(path, content=csv, headers=headers)


def test_parser_normalization_validation_and_limits():
    rows, ignored = parse_csv(b'\xef\xbb\xbf Company , EMAIL,source,organization_id\r\n"A, Inc",a@example.com,csv,999\r\n\r\nB,a@example.com,csv,888\r\nC,nope,csv,777\r\n')
    assert ignored == ["organization_id"]
    assert [row.status for row in rows] == ["ready", "duplicate", "invalid"]
    assert rows[0].company == "A, Inc"
    assert rows[2].errors
    multiline, _ = parse_csv(b'company,email,source\n"Line\nBreak",line@example.com,csv\nMissing,,csv\nLong,' + b"a" * 202 + b"@example.com,csv\n")
    assert multiline[0].company == "Line\nBreak"
    assert multiline[1].errors == ["Email is required."]
    assert "Email is invalid." in multiline[2].errors
    long_company, _ = parse_csv(b"company,email,source\n" + b"A" * 201 + b",long@example.com,csv\n")
    assert long_company[0].errors == ["Company is too long."]
    for content in [b"", b"company,email,source\n", b"company,email\nx,x\n", b"company,Company,email,source\nx,x,x,x\n", b'company,email,source\n"broken']:
        try:
            parse_csv(content)
            assert False, content
        except ImportValidationError:
            pass
    try:
        parse_csv(b"company,email,source\n" + b"A,a@example.com,csv\n" * 1001)
        assert False
    except ImportValidationError:
        pass
    try:
        parse_csv(b"a" * (1024 * 1024 + 1))
        assert False
    except ImportValidationError:
        pass


def test_preview_confirm_tenant_isolation_and_no_ai(tenant_workspace, monkeypatch):
    from backend.services import lead_processing_service
    monkeypatch.setattr(lead_processing_service.LeadProcessingService, "process", lambda *args: (_ for _ in ()).throw(AssertionError("AI called")))
    csv = b"company,email,source,organization_id\nOther Tenant,alpha-lead@example.com,csv,999\nNew,new@example.com,csv,999\nBad,bad-email,csv,999\nAgain,new@example.com,csv,999\n"
    preview_path = "/api/imports/leads/preview"
    confirm_path = "/api/imports/leads/confirm"
    assert _post(tenant_workspace, preview_path, csv, user="a", org="b").status_code == 403
    assert _post(tenant_workspace, confirm_path, csv, user="a", org="b", token="untrusted").status_code == 403
    assert tenant_workspace["clients"]["a"].post(preview_path, content=csv, headers={"Content-Type": "text/csv", "X-CSRF-Token": _headers(tenant_workspace)["X-CSRF-Token"]}).status_code == 400
    assert tenant_workspace["clients"]["a"].post(preview_path, content=csv, headers={"Content-Type": "text/csv", "X-Organization-ID": _headers(tenant_workspace)["X-Organization-ID"]}).status_code == 403
    preview_b = _post(tenant_workspace, preview_path, csv, user="b", org="b")
    assert preview_b.status_code == 200, preview_b.text
    assert preview_b.json()["summary"] == {"total": 4, "ready": 2, "duplicates": 1, "invalid": 1}
    with SessionLocal() as db:
        assert db.query(Lead).filter(Lead.email == "new@example.com").count() == 0
    assert _post(tenant_workspace, confirm_path, csv, user="a", org="a", token=preview_b.json()["token"]).status_code == 422
    assert _post(tenant_workspace, confirm_path, csv + b"\n", user="b", org="b", token=preview_b.json()["token"]).status_code == 422
    result = _post(tenant_workspace, confirm_path, csv, user="b", org="b", token=preview_b.json()["token"])
    assert result.status_code == 200, result.text
    assert result.json() == {"total": 4, "imported": 2, "duplicates": 1, "invalid": 1}
    double = _post(tenant_workspace, confirm_path, csv, user="b", org="b", token=preview_b.json()["token"])
    assert double.json() == {"total": 4, "imported": 0, "duplicates": 3, "invalid": 1}
    preview_a = _post(tenant_workspace, preview_path, csv, user="a", org="a")
    assert preview_a.json()["summary"]["duplicates"] == 2
    with SessionLocal() as db:
        imported = db.query(Lead).filter(Lead.organization_id == tenant_workspace["ids"]["organizations"]["b"], Lead.email == "new@example.com").one()
        assert imported.status == "New" and imported.processing_status == "pending"
        assert imported.lead_score is None and imported.priority is None
        assert db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == imported.id).count() == 0


def test_preview_errors_and_race(tenant_workspace, monkeypatch):
    from backend.services import lead_import_service
    csv = b"company,email,source\nRace,race@example.com,csv\n"
    path = "/api/imports/leads/preview"
    assert _post(tenant_workspace, path, b"", user="a").status_code == 422
    assert _post(tenant_workspace, path, csv, user="a").status_code == 200
    assert _post(tenant_workspace, path, csv, user="a", org="b").status_code == 403
    preview = _post(tenant_workspace, path, csv).json()
    now = lead_import_service.time.time()
    monkeypatch.setattr(lead_import_service.time, "time", lambda: now + 901)
    assert _post(tenant_workspace, "/api/imports/leads/confirm", csv, token=preview["token"]).status_code == 422
    monkeypatch.undo()
    with SessionLocal() as db:
        db.add(Lead(organization_id=tenant_workspace["ids"]["organizations"]["a"], company="Racer", email="race@example.com", source="manual"))
        db.commit()
    result = _post(tenant_workspace, "/api/imports/leads/confirm", csv, token=preview["token"])
    assert result.json() == {"total": 1, "imported": 0, "duplicates": 1, "invalid": 0}
