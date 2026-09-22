import json

from backend.ai.orchestrator import AIOrchestrator
from backend.ai.prompts.contact_prompt import build_contact_prompt


class ContactAgent:

    def __init__(self):
        self.ai = AIOrchestrator()

    def analyze(self, email: str):

        prompt = build_contact_prompt(email)

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