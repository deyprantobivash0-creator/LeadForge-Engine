from backend.database.base import Base
from backend.database.session import engine
from backend.models.lead_analysis import LeadAnalysis

# Import all models here
from backend.models.lead import Lead

print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Database created successfully.")