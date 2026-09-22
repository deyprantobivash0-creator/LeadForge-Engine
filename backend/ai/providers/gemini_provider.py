from google import genai

from backend.core.config import settings
from backend.ai.providers.base_provider import AIProvider


class GeminiProvider(AIProvider):

    def __init__(self):

        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

    def generate(self, prompt: str) -> str:

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        return response.text