from backend.database.session import SessionLocal
from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


db = SessionLocal()

try:

    result = LeadAnalysisRepository.create(
        db=db,
        company="Test Company",
        email="analysis@testcompany.com",
        priority="High",
        lead_score=85,
        result={
            "industry": "Technology",
            "company_size": "Enterprise",
            "lead_score": 85,
            "priority": "High",
            "recommendation": "Contact decision maker",
        },
    )

    print("\n====== ANALYSIS CREATED ======")
    print("ID:", result.id)
    print("Company:", result.company)
    print("Email:", result.email)
    print("Priority:", result.priority)
    print("Lead Score:", result.lead_score)
    print("Result:", result.result)

finally:
    db.close()