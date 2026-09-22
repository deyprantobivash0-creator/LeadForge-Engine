from backend.ai.providers.gemini_provider import GeminiProvider
from backend.ai.providers.mock_provider import MockProvider

from backend.core.config import settings


class AIRouter:

    def get_provider(self):

        provider = settings.AI_PROVIDER.lower()

        if provider == "mock":
            return MockProvider()

        return GeminiProvider()