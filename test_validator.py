from backend.ingestion.validator import LeadValidator

validator = LeadValidator()

samples = [

    {
        "company": "Tesla",
        "email": "sales@tesla.com",
        "source": "Website"
    },

    {
        "company": "",
        "email": "wrong-email",
        "source": ""
    },

]

for i, lead in enumerate(samples, start=1):

    valid, errors = validator.validate(lead)

    print(f"\nLead {i}")

    print("Valid:", valid)

    print("Errors:", errors)