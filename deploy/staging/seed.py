"""Manual staging-only synthetic QA fixture, never an application startup task."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, "/app")


def main():
    if os.environ.get("LEADFORGE_STAGE_SEED") != "synthetic-only":
        raise ValueError("Explicit synthetic seed confirmation required")
    from sqlalchemy.engine import URL
    password = Path("/run/secrets/app_password").read_text().strip()
    qa_password = Path("/run/secrets/qa_password").read_text().strip()
    os.environ["DATABASE_URL"] = URL.create("postgresql+psycopg", username="leadforge_stage_app",
        password=password, host="postgres", database="leadforge_stage").render_as_string(hide_password=False)
    seed(qa_password)


def seed(qa_password):
    from backend.core.config import settings
    if not (settings.ENVIRONMENT == "production" and settings.LEADFORGE_STAGING and settings.AI_PROVIDER == "mock"):
        raise ValueError("Strict staging configuration required")
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from backend.core.passwords import hash_password, verify_password
    from backend.database.session import SessionLocal
    from backend.models import User, Organization, OrganizationMembership, Lead, LeadAnalysis
    with SessionLocal() as db, db.begin():
        stamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        fixtures = []
        for index, key in enumerate(("alpha", "beta")):
            email = f"staging-synthetic-{key}@example.com"
            user = db.scalar(select(User).where(User.email == email))
            org = db.scalar(select(Organization).where(Organization.slug == "staging-synthetic-" + key))
            if user is None and org is None:
                user = User(email=email, password_hash=hash_password(qa_password))
                org = Organization(name="STAGING SYNTHETIC " + key, slug="staging-synthetic-" + key)
                db.add_all([user, org]); db.flush()
                db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role="owner"))
                for number in range(2):
                    lead = Lead(organization_id=org.id, company=f"SYNTHETIC 東京 বাংলা café {key} {number}",
                        email=f"staging-{key}-{number}@example.com", source="staging-synthetic", status=("New", "Won")[number],
                        processing_status="completed", lead_score=20 + number, priority="Cold", created_at=stamp)
                    db.add(lead); db.flush()
                    for score in (10, 20 + number):
                        db.add(LeadAnalysis(organization_id=org.id, lead_id=lead.id, company=lead.company,
                            email=lead.email, lead_score=score, priority="Cold", result={"synthetic": True}, created_at=stamp))
            elif user is None or org is None or not verify_password(qa_password, user.password_hash):
                raise ValueError("Unexpected existing synthetic fixture; refusing overwrite")
            if not db.scalar(select(OrganizationMembership.id).where(OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == org.id)):
                raise ValueError("Unexpected fixture membership")
            lead_ids = list(db.scalars(select(Lead.id).where(Lead.organization_id == org.id).order_by(Lead.id)))
            fixtures.append({"email": email, "organization_id": org.id, "lead_ids": lead_ids})
        print(json.dumps({"synthetic": True, "fixtures": fixtures}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Synthetic staging seed failed; no fixture credentials printed", file=sys.stderr)
        raise SystemExit(1) from None
