from pprint import pprint

from backend.database.session import SessionLocal
from backend.dashboard.dashboard_service import DashboardService


db = SessionLocal()

try:

    service = DashboardService(db)

    dashboard = service.overview()

    print("\n========================================")
    print("LEADFORGE DASHBOARD OVERVIEW")
    print("========================================")

    pprint(dashboard)

finally:

    db.close()