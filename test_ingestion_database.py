from pprint import pprint

from backend.ingestion.ingestion_service import IngestionService


CSV_FILE = "sample_leads.csv"


service = IngestionService()

result = service.ingest(CSV_FILE)

print("\n========================================")
print("LEADFORGE INGESTION + DATABASE TEST")
print("========================================")

print("\nTotal rows:")
print(result["total_rows"])

print("\nValid leads:")
print(result["valid_count"])

print("\nInvalid leads:")
print(result["invalid_count"])

print("\n====== SAVED ANALYSES ======")

for analysis in result["analysis_results"]:

    print("\n----------------------------------------")

    print("Analysis ID:", analysis["analysis_id"])
    print("Company:", analysis["company"])
    print("Email:", analysis["email"])
    print("Priority:", analysis["priority"])
    print("Lead Score:", analysis["lead_score"])

    print("\nComplete Result:")
    pprint(analysis["result"])