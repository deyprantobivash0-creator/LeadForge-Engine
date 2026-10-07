"""Local Ollama adapter; availability and model installation require manual checks."""

import httpx
import os

from backend.ai.providers.base import AIProvider, ProviderNotConfigured, ProviderTimeout, ProviderUnavailable
from backend.core.config import settings


class OllamaProvider(AIProvider):
    async def generate(self, prompt: str) -> str:
        if os.environ.get("LEADFORGE_CI") == "1":
            raise ProviderNotConfigured("Real AI providers are forbidden in CI")
        if not settings.OLLAMA_HOST or not settings.OLLAMA_MODEL:
            raise ProviderNotConfigured("Ollama host or model is not configured")
        try:
            async with httpx.AsyncClient(timeout=settings.AI_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.OLLAMA_HOST.rstrip('/')}/api/generate",
                    json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                )
                response.raise_for_status()
                content = response.json().get("response")
                if not isinstance(content, str) or not content:
                    raise ProviderUnavailable("Ollama returned an empty response")
                return content
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("Ollama timed out") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable("Ollama request failed") from exc
