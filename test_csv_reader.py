from pprint import pprint

from backend.ingestion.csv_reader import CSVReader

reader = CSVReader()

rows = reader.read("sample_leads.csv")

print(f"Total Rows: {len(rows)}")
print()

pprint(rows)