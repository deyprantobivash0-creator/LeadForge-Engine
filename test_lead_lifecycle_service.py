from datetime import datetime, timedelta

from backend.database.session import SessionLocal
from backend.services.lead_lifecycle_service import (
    LeadLifecycleService,
)


db = SessionLocal()

try:

    service = LeadLifecycleService(db)

    lead = service.update_lifecycle(
        lead_id=1,
        status="Contacted",
        notes="Initial outreach sent.",
        last_contacted=datetime.utcnow(),
        next_follow_up=datetime.utcnow() + timedelta(days=3),
    )

    if not lead:
        print("Lead not found.")
    else:
        print("\n========================================")
        print("LEAD LIFECYCLE SERVICE TEST")
        print("========================================")

        print("ID:", lead.id)
        print("Company:", lead.company)
        print("Status:", lead.status)
        print("Notes:", lead.notes)
        print("Last Contacted:", lead.last_contacted)
        print("Next Follow-Up:", lead.next_follow_up)

finally:

    db.close()