from backend.ai.providers.base import AIProvider, ProviderNotConfigured


class DeepSeekProvider(AIProvider):

    async def generate(self, prompt: str) -> str:
        raise ProviderNotConfigured("DeepSeek integration is not available")

    async def generate_structured(self, prompt, schema):
        raise ProviderNotConfigured("DeepSeek integration is not available")
