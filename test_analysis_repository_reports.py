from backend.database.session import SessionLocal
from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


db = SessionLocal()

try:

    repository = LeadAnalysisRepository()

    print("\n====== REPORTING REPOSITORY TEST ======")

    total = repository.count(db)

    high = repository.count_by_priority(
        db,
        "High",
    )

    average_score = repository.average_lead_score(
        db
    )

    analyses = repository.get_all(db)

    print("Total Analyses:", total)

    print("High Priority:", high)

    print("Average Lead Score:", average_score)

    print("\nRecent Analyses:")

    for analysis in analyses[:5]:

        print(
            analysis.id,
            "|",
            analysis.company,
            "|",
            analysis.priority,
            "|",
            analysis.lead_score,
        )

finally:

    db.close()