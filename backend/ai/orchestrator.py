from backend.ai.providers.router import AIRouter

class AIOrchestrator:
    def __init__(self, provider):
        self.provider = provider

    async def generate(self, prompt: str) -> str:
        """
        Plain text generation.
        Used by legacy agents and compatibility layer.
        """
        return await self.provider.generate(prompt)

    async def generate_structured(self, prompt: str, schema):
        """
        Structured Pydantic generation.
        Used by the Lead Brain workflow.
        """
        return await self.provider.generate_structured(prompt, schema)
