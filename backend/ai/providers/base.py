from abc import ABC, abstractmethod
from typing import Any, Type
from pydantic import ValidationError


class ProviderError(Exception):
    code = "provider_unavailable"


class ProviderNotConfigured(ProviderError):
    code = "provider_not_configured"


class ProviderTimeout(ProviderError):
    code = "provider_timeout"


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"


class ProviderMalformedOutput(ProviderError):
    code = "malformed_provider_output"


class AIProvider(ABC):

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Return plain-text completion."""
        pass

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[Any],
    ):
        """Return a validated Pydantic object; never accept raw model text."""
        raw = await self.generate(prompt)
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProviderMalformedOutput("Provider returned invalid structured output") from exc
