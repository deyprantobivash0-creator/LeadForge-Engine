from backend.ingestion.csv_reader import CSVReader
from backend.ingestion.validator import LeadValidator
from backend.graph.workflow import graph

from backend.database.session import SessionLocal
from backend.services.analysis_service import AnalysisService


class IngestionService:

    def __init__(self):
        self.reader = CSVReader()
        self.validator = LeadValidator()

    def ingest(self, file_path: str):

        rows = self.reader.read(file_path)

        valid_leads = []
        invalid_leads = []
        analysis_results = []

        db = SessionLocal()

        try:

            analysis_service = AnalysisService(db)

            for index, lead in enumerate(rows, start=2):

                is_valid, errors = self.validator.validate(lead)

                if is_valid:

                    valid_leads.append(lead)

                    # Run LeadForge AI workflow
                    result = graph.invoke({
                        "company": lead["company"],
                        "email": lead["email"],
                    })

                    # Save complete AI analysis to database
                    saved_analysis = analysis_service.save_analysis(
                        company=lead["company"],
                        email=lead["email"],
                        result=result,
                    )

                    analysis_results.append({
                        "analysis_id": saved_analysis.id,
                        "company": saved_analysis.company,
                        "email": saved_analysis.email,
                        "priority": saved_analysis.priority,
                        "lead_score": saved_analysis.lead_score,
                        "result": saved_analysis.result,
                    })

                else:

                    invalid_leads.append({
                        "row": index,
                        "lead": lead,
                        "errors": errors,
                    })

            return {
                "total_rows": len(rows),
                "valid_count": len(valid_leads),
                "invalid_count": len(invalid_leads),
                "valid_leads": valid_leads,
                "invalid_leads": invalid_leads,
                "analysis_results": analysis_results,
            }

        finally:

            db.close()