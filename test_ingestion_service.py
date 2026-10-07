from pprint import pprint

from backend.ingestion.ingestion_service import IngestionService

service = IngestionService()

result = service.ingest("sample_leads_invalid.csv")

print("\n=== SUMMARY ===")
print(f"Total Rows: {result['total_rows']}")
print(f"Valid: {result['valid_count']}")
print(f"Invalid: {result['invalid_count']}")

print("\n=== VALID LEADS ===")
print("\n=== ANALYSIS RESULTS ===")

for result in result["analysis_results"]:

    print("-" * 50)

    print(result["company"])

    print(result["final_decision"])


print("\n=== INVALID LEADS ===")
pprint(result["invalid_leads"])