from backend.services.ai_qualification_service import AIQualificationService

service = AIQualificationService()

result = service.qualify(
    "Tesla",
    "sales@tesla.com"
)

print(result)