import json

from backend.ai.orchestrator import AIOrchestrator
from backend.ai.prompts.contact_prompt import build_contact_prompt


class ContactAgent:

    def __init__(self):
        self.ai = AIOrchestrator()

    async def analyze(self, contact):

        prompt = build_contact_prompt(contact)

        response = await self.ai.generate(prompt)

        cleaned = response.strip()

        if cleaned.startswith("```"):
            cleaned = (
                cleaned
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        return json.loads(cleaned)