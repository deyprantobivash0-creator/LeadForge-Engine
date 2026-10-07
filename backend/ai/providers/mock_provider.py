"""Explicit development/test provider. It never asserts external facts."""

import json

from backend.ai.providers.base import AIProvider, ProviderTimeout, ProviderUnavailable


class MockProvider(AIProvider):
    def __init__(self, mode: str = "success"):
        self.mode = mode
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.mode == "timeout":
            raise ProviderTimeout("Mock timeout")
        if self.mode == "error":
            raise ProviderUnavailable("Mock provider unavailable")
        if self.mode == "malformed":
            return '{"score": "invalid"}'
        # The score reflects insufficient evidence, not a negative buying signal.
        return json.dumps({
            "score": 0,
            "summary": "Insufficient supplied data for a supported assessment.",
            "evidence": [],
        })
