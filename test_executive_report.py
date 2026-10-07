from pprint import pprint

from backend.database.session import SessionLocal
from backend.reports.report_service import ReportService


db = SessionLocal()

try:

    service = ReportService(db)

    report = service.weekly_report()

    executive = service.executive_summary(
        report
    )

    print("\n========================================")
    print("LEADFORGE EXECUTIVE REPORT")
    print("========================================")

    pprint(executive)

finally:

    db.close()