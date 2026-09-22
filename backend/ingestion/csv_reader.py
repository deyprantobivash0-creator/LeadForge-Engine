import csv
from pathlib import Path


class CSVReader:

    def read(self, file_path: str) -> list[dict]:
        """
        Reads a CSV file and returns a list of dictionaries.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {file_path}"
            )

        rows = []

        with open(
            path,
            mode="r",
            newline="",
            encoding="utf-8"
        ) as csvfile:

            reader = csv.DictReader(csvfile)

            for row in reader:
                rows.append(
                    {
                        "company": row.get("company", "").strip(),
                        "email": row.get("email", "").strip(),
                        "source": row.get("source", "").strip(),
                    }
                )

        return rows