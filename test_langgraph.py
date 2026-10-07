from pprint import pprint
import time

from backend.graph.workflow import graph
from backend.database.session import SessionLocal
from backend.services.analysis_service import AnalysisService


company = "Tesla"
email = "sales@tesla.com"


print("\n========================================")
print("LEADFORGE LANGGRAPH + DATABASE TEST")
print("========================================")


# Create database session
db = SessionLocal()

try:

    # Start timer
    start = time.perf_counter()

    # Run LangGraph
    result = graph.invoke(
        {
            "company": company,
            "email": email,
        }
    )

    # Calculate execution time
    elapsed = time.perf_counter() - start

    print("\n====== LANGGRAPH RESULT ======")

    pprint(result)

    print(
        f"\nExecution Time: {elapsed:.3f} sec"
    )

    # Create analysis service
    analysis_service = AnalysisService(db)

    # Save LangGraph result
    saved_analysis = analysis_service.save_analysis(
        company=company,
        email=email,
        result=result,
    )

    print("\n====== DATABASE RESULT ======")

    print("Analysis ID:", saved_analysis.id)
    print("Company:", saved_analysis.company)
    print("Email:", saved_analysis.email)
    print("Priority:", saved_analysis.priority)
    print("Lead Score:", saved_analysis.lead_score)
    print("Created:", saved_analysis.created_at)

finally:

    db.close()