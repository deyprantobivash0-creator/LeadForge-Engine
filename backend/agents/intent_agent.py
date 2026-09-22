import json

from backend.ai.orchestrator import AIOrchestrator
from backend.ai.prompts.intent_prompt import build_intent_prompt


class IntentAgent:

    def __init__(self):
        self.ai = AIOrchestrator()

    def analyze(self, company: str, email: str):

        prompt = build_intent_prompt(company, email)

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