from backend.ai.providers.router import AIRouter

class AIOrchestrator:

    def __init__(self):
        self.provider = AIRouter().get_provider()

    def generate(self, prompt: str):
        return self.provider.generate(prompt)
