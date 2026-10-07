"""Google Gen AI SDK adapter; network use requires explicit Gemini selection."""

import asyncio
import os
import httpx

from backend.ai.providers.base import AIProvider, ProviderNotConfigured, ProviderTimeout, ProviderUnavailable
from backend.core.config import settings, secret_value


class GeminiProvider(AIProvider):
    async def generate(self, prompt: str) -> str:
        if os.environ.get("LEADFORGE_CI") == "1":
            raise ProviderNotConfigured("Real AI providers are forbidden in CI")
        if not settings.GEMINI_API_KEY:
            raise ProviderNotConfigured("Gemini API key is not configured")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=secret_value(settings.GEMINI_API_KEY),
                http_options=types.HttpOptions(timeout=settings.AI_TIMEOUT_SECONDS * 1000),
            )
            try:
                async with client.aio as async_client:
                    response = await async_client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
            finally:
                client.close()
            if not response.text:
                raise ProviderUnavailable("Gemini returned an empty response")
            return response.text
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderTimeout("Gemini timed out") from exc
        except (ProviderNotConfigured, ProviderUnavailable):
            raise
        except Exception as exc:
            raise ProviderUnavailable("Gemini request failed") from exc
