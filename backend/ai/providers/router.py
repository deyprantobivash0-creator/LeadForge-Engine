from backend.core.config import settings
from backend.ai.providers.base import ProviderNotConfigured


class AIRouter:

    def get_provider(self):

        provider = settings.AI_PROVIDER.lower()

        if provider == "mock":
            if settings.ENVIRONMENT.lower() not in {"development", "test"} and not settings.LEADFORGE_STAGING:
                raise ProviderNotConfigured("Mock provider is restricted to development/test")
            from backend.ai.providers.mock_provider import MockProvider
            return MockProvider()

        if provider == "gemini":
            from backend.ai.providers.gemini_provider import GeminiProvider
            return GeminiProvider()

        if provider == "deepseek":
            from backend.ai.providers.deepseek_provider import DeepSeekProvider
            return DeepSeekProvider()

        if provider == "ollama":
            from backend.ai.providers.ollama_provider import OllamaProvider
            return OllamaProvider()

        raise ProviderNotConfigured("Selected AI provider is unsupported")
