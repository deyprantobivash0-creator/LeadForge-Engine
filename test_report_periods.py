from pprint import pprint

from backend.database.session import SessionLocal
from backend.reports.report_service import ReportService


db = SessionLocal()

try:

    service = ReportService(db)

    print("\n========================================")
    print("LEADFORGE REPORT PERIOD TEST")
    print("========================================")

    print("\n====== DAILY REPORT ======")

    daily = service.daily_report()
    pprint(daily)

    print("\n====== WEEKLY REPORT ======")

    weekly = service.weekly_report()
    pprint(weekly)

    print("\n====== MONTHLY REPORT ======")

    monthly = service.monthly_report()
    pprint(monthly)

finally:

    db.close()