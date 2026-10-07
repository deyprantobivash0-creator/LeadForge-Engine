"""Legacy entry point retained for import compatibility; no direct API access."""


def ask_gemini(prompt: str):
    raise RuntimeError("Legacy Gemini client is disabled; use LeadProcessingService")
