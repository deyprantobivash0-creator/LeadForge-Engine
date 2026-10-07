from pprint import pprint

from backend.database.session import SessionLocal
from backend.services.lead_intelligence_service import (
    LeadIntelligenceService,
)


db = SessionLocal()

try:

    service = LeadIntelligenceService(db)

    print("\n========================================")
    print("LEAD INTELLIGENCE SERVICE TEST")
    print("========================================")

    result = service.get_by_id(1)

    pprint(result)

finally:

    db.close()