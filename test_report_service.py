from datetime import datetime, timedelta
from pprint import pprint

from backend.database.session import SessionLocal
from backend.reports.report_service import ReportService


db = SessionLocal()

try:

    service = ReportService(db)

    end_date = datetime.utcnow() + timedelta(days=1)
    start_date = datetime.utcnow() - timedelta(days=30)

    report = service.generate_report(
        start_date=start_date,
        end_date=end_date,
        period="last_30_days",
    )

    print("\n========================================")
    print("LEADFORGE REPORT SERVICE TEST")
    print("========================================")

    print("\nPeriod:", report["period"])

    print("Total Leads:", report["total_leads"])

    print("Hot Leads:", report["hot_leads"])

    print("Warm Leads:", report["warm_leads"])

    print("Cold Leads:", report["cold_leads"])

    print(
        "Average Lead Score:",
        report["average_lead_score"],
    )

    print("\n====== TOP LEADS ======")

    pprint(report["top_leads"])

finally:

    db.close()