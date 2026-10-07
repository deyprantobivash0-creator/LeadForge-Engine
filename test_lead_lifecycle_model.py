from datetime import datetime, timedelta

from backend.database.session import SessionLocal
from backend.repositories.lead_repository import LeadRepository


db = SessionLocal()

try:

    repository = LeadRepository(db)

    lead = repository.get_lead_by_id(1)

    if not lead:
        print("No lead with ID 1 found.")
    else:

        lead.status = "Qualified"
        lead.notes = "Lifecycle model test"
        lead.last_contacted = datetime.utcnow()
        lead.next_follow_up = (
            datetime.utcnow() + timedelta(days=3)
        )

        db.commit()
        db.refresh(lead)

        print("\n========================================")
        print("LEAD LIFECYCLE MODEL TEST")
        print("========================================")

        print("ID:", lead.id)
        print("Company:", lead.company)
        print("Status:", lead.status)
        print("Notes:", lead.notes)
        print("Last Contacted:", lead.last_contacted)
        print("Next Follow-Up:", lead.next_follow_up)

finally:

    db.close()