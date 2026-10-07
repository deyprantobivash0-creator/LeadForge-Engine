from pprint import pprint

from backend.database.session import SessionLocal
from backend.services.analysis_service import AnalysisService


db = SessionLocal()

try:

    service = AnalysisService(db)

    ai_result = {
        "industry": "Technology",
        "company_size": "Enterprise",
        "lead_score": 88,
        "priority": "High",
        "recommendation": "Contact decision maker",
    }

    saved = service.save_analysis(
        company="D2Desk Test Company",
        email="test@d2desk.com",
        result=ai_result,
    )

    print("\n====== ANALYSIS SAVED ======")

    print("ID:", saved.id)
    print("Company:", saved.company)
    print("Email:", saved.email)
    print("Priority:", saved.priority)
    print("Lead Score:", saved.lead_score)
    print("Created:", saved.created_at)

    print("\n====== STORED RESULT ======")

    pprint(saved.result)

finally:

    db.close()