import json

from backend.ai.orchestrator import AIOrchestrator
from backend.ai.prompts.qualification_prompt import build_prompt


class AIQualificationService:

    def __init__(self):
        self.ai = AIOrchestrator()

    def qualify(self, company: str, email: str):

        prompt = build_prompt(company, email)

        response = self.ai.generate(prompt)

        cleaned = response.strip()

        if cleaned.startswith("```"):
            cleaned = (
                cleaned
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        return json.loads(cleaned)