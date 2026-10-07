from backend.database.session import SessionLocal
from backend.repositories.lead_repository import LeadRepository


db = SessionLocal()

try:

    repository = LeadRepository(db)

    print("\n========================================")
    print("LEAD REPOSITORY DETAIL TEST")
    print("========================================")

    # Test existing lead
    lead = repository.get_lead_by_id(1)

    if lead:
        print("\nLead by ID:")
        print("ID:", lead.id)
        print("Company:", lead.company)
        print("Email:", lead.email)
        print("Source:", lead.source)
    else:
        print("\nNo lead found with ID 1")

    # Test email lookup
    if lead:
        found_by_email = repository.get_lead_by_email(
            lead.email
        )

        print("\nLead by Email:")

        if found_by_email:
            print("ID:", found_by_email.id)
            print("Company:", found_by_email.company)
            print("Email:", found_by_email.email)
            print("Source:", found_by_email.source)

finally:

    db.close()