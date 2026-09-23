from backend.utils.normalization import (
    normalize_company,
    normalize_email,
    normalize_source,
    normalize_status,
)


class LeadNormalizationService:

    def normalize(self, data: dict) -> dict:
        return {
            **data,
            "company": normalize_company(data["company"]),
            "email": normalize_email(data["email"]),
            "source": normalize_source(data.get("source", "api")),
            "status": normalize_status(data.get("status")),
        }