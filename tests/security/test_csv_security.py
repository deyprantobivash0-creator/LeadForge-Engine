import csv
import io
import pytest
from backend.core.csv_security import spreadsheet_cell
from backend.services.lead_import_service import parse_csv, ImportValidationError


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-cmd", "@SUM(A1)", " \t=1", "\x00=1", "\u00a0\x01=1", "\tplain", "\rplain", "\nplain", '="quoted,formula"'])
def test_formula_cells_round_trip_inert(value):
    buffer = io.StringIO()
    csv.writer(buffer).writerow([spreadsheet_cell(value)])
    assert next(csv.reader(io.StringIO(buffer.getvalue())))[0] == "'" + value


@pytest.mark.parametrize("content", [b"", b"\xff", b"company,email,source,company\nA,a@example.com,x,x",
    b'company,email,source\n"unterminated,a@example.com,x',
    b"company,email,source\n" + b"A,a@example.com,x\n"*1001,
    b"x"*(1024*1024+1), b"company,email,source\nA\x00,a@example.com,x"],
    ids=["empty", "invalid-utf8", "duplicate-header", "malformed-quote", "row-limit", "byte-limit", "nul"])
def test_malicious_csv_is_bounded(content):
    with pytest.raises(ImportValidationError):
        parse_csv(content)


def test_csv_values_are_data_and_invalid_rows_stay_invalid():
    rows, _ = parse_csv(b'company,email,source\n"<script>alert(1)</script>",a@example.com,=cmd\nA,not-email,x\nB,b@example.com,x,extra')
    assert rows[0].company == "<script>alert(1)</script>" and rows[0].source == "=cmd"
    assert rows[0].status == "ready"
    assert rows[1].status == rows[2].status == "invalid"


def test_wide_csv_keeps_extra_headers_inert_and_required_fields_correct():
    extra = [f"untrusted-{i}" for i in range(1000)]
    header = extra + ["company", "email", "source"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerow(["ignored"]*len(extra) + ["Safe", "wide@example.com", "fixture"])
    rows, ignored = parse_csv(buffer.getvalue().encode())
    assert ignored == extra
    assert len(rows) == 1 and rows[0].status == "ready"
    assert rows[0].company == "Safe" and rows[0].email == "wide@example.com"
