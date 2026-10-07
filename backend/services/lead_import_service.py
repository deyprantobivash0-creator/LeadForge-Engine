from backend.core.logger import operation
"""Bounded CSV preview and explicit, session-bound import confirmation."""

import base64
import csv
import hashlib
import hmac
import io
import json
import time

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.repositories.lead_import_repository import LeadImportRepository
from backend.schemas.import_schema import ImportPreview, ImportResult, ImportRow, ImportSummary
from backend.schemas.lead_schema import LeadCreate


MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 1000
PREVIEW_ROWS = 100
TOKEN_SECONDS = 15 * 60
HEADERS = ("company", "email", "source")


class ImportValidationError(ValueError):
    pass


def parse_csv(content: bytes) -> tuple[list[ImportRow], list[str]]:
    if not content:
        raise ImportValidationError("CSV file is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise ImportValidationError("CSV file exceeds the 1 MB limit.")
    if b"\x00" in content:
        raise ImportValidationError("CSV must not contain NUL bytes.")
    try:
        stream = io.StringIO(content.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as exc:
        raise ImportValidationError("CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.reader(stream, strict=True)
        raw_headers = next(reader, None)
        if not raw_headers:
            raise ImportValidationError("CSV file needs a header row.")
        headers = [value.strip().lower() for value in raw_headers]
        if len(headers) != len(set(headers)):
            raise ImportValidationError("CSV has duplicate headers.")
        if not set(HEADERS).issubset(headers):
            raise ImportValidationError("CSV needs company, email, and source headers.")
        # Resolve once: hostile wide headers must not cause a full header scan
        # for each field of every row. Work stays linear in bounded CSV input.
        positions = {key: headers.index(key) for key in HEADERS}
        ignored = [raw_headers[i].strip() for i, value in enumerate(headers) if value not in HEADERS]
        rows: list[ImportRow] = []
        seen: set[str] = set()
        for values in reader:
            if not values or all(not value.strip() for value in values):
                continue
            if len(rows) >= MAX_ROWS:
                raise ImportValidationError("CSV exceeds the 1,000 row limit.")
            data = {key: values[index].strip() if index < len(values) else ""
                    for key, index in positions.items()}
            errors = []
            if len(values) != len(headers):
                errors.append("Column count does not match header.")
            for key in HEADERS:
                if not data[key]:
                    errors.append(f"{key.capitalize()} is required.")
            if not errors:
                try:
                    validated = LeadCreate.model_validate(data)
                    data = validated.model_dump(mode="json")
                except ValidationError as exc:
                    for issue in exc.errors():
                        field = str(issue["loc"][0]).capitalize()
                        if issue["type"] == "string_too_long":
                            errors.append(f"{field} is too long.")
                        elif field == "Email":
                            errors.append("Email is invalid.")
                        else:
                            errors.append(f"{field} is invalid.")
            status = "invalid" if errors else "ready"
            if status == "ready":
                if data["email"] in seen:
                    status = "duplicate"
                    errors.append("Repeated email in this CSV.")
                else:
                    seen.add(data["email"])
            rows.append(ImportRow(row_number=reader.line_num, **data, status=status, errors=errors))
    except csv.Error as exc:
        raise ImportValidationError("Malformed CSV file.") from exc
    if not rows:
        raise ImportValidationError("CSV contains no data rows.")
    return rows, ignored


class LeadImportService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadImportRepository(db)

    def _evaluate(self, content: bytes, organization_id: int):
        rows, ignored = parse_csv(content)
        candidates = {row.email for row in rows if row.status == "ready"}
        existing = self.repository.existing_emails(organization_id, candidates)
        for row in rows:
            if row.status == "ready" and row.email in existing:
                row.status = "duplicate"
                row.errors.append("Email already exists in this workspace.")
        summary = ImportSummary(
            total=len(rows),
            ready=sum(row.status == "ready" for row in rows),
            duplicates=sum(row.status == "duplicate" for row in rows),
            invalid=sum(row.status == "invalid" for row in rows),
        )
        return rows, ignored, summary

    @staticmethod
    def _signature(payload: str, session_key: str) -> str:
        return hmac.new(bytes.fromhex(session_key), payload.encode(), hashlib.sha256).hexdigest()

    @operation("import.preview")
    def preview(self, content: bytes, organization_id: int, user_id: int, session_key: str) -> ImportPreview:
        rows, ignored, summary = self._evaluate(content, organization_id)
        payload = base64.urlsafe_b64encode(json.dumps({
            "digest": hashlib.sha256(content).hexdigest(),
            "organization": organization_id,
            "user": user_id,
            "expires": int(time.time()) + TOKEN_SECONDS,
        }, separators=(",", ":")).encode()).decode()
        token = f"{payload}.{self._signature(payload, session_key)}"
        return ImportPreview(token=token, summary=summary, rows=rows[:PREVIEW_ROWS],
                             preview_limit=PREVIEW_ROWS, ignored_headers=ignored)

    @operation("import.confirm")
    def confirm(self, content: bytes, token: str, organization_id: int,
                user_id: int, session_key: str) -> ImportResult:
        try:
            payload, signature = token.split(".", 1)
            if not hmac.compare_digest(signature, self._signature(payload, session_key)):
                raise ValueError
            claims = json.loads(base64.urlsafe_b64decode(payload))
            if (claims["organization"] != organization_id or claims["user"] != user_id
                    or claims["expires"] < time.time()
                    or claims["digest"] != hashlib.sha256(content).hexdigest()):
                raise ValueError
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ImportValidationError("Preview expired or file changed. Preview the CSV again.") from exc
        rows, _, summary = self._evaluate(content, organization_id)
        imported = 0
        raced = 0
        try:
            for row in rows:
                if row.status != "ready":
                    continue
                try:
                    with self.db.begin_nested():
                        self.repository.add(organization_id, row.company, row.email, row.source)
                    imported += 1
                except IntegrityError as exc:
                    # Only the tenant/email uniqueness conflict is a normal duplicate.
                    if self.db.get_bind().dialect.name == "postgresql":
                        diagnostic = getattr(exc.orig, "diag", None)
                        if (getattr(exc.orig, "sqlstate", None) != "23505"
                                or getattr(diagnostic, "constraint_name", None)
                                != "uq_leads_organization_email"):
                            raise
                    elif row.email not in self.repository.existing_emails(organization_id, {row.email}):
                        raise
                    raced += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ImportResult(total=summary.total, imported=imported,
                            duplicates=summary.duplicates + raced, invalid=summary.invalid)
