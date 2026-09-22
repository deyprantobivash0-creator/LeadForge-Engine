import json

from backend.ai.orchestrator import AIOrchestrator
from backend.ai.prompts.company_prompt import build_company_prompt


class CompanyAgent:

    def __init__(self):
        self.ai = AIOrchestrator()

    def analyze(self, company: str):

        prompt = build_company_prompt(company)

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