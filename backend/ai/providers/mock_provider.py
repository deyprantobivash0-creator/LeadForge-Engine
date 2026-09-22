from backend.ai.providers.base_provider import AIProvider


class MockProvider(AIProvider):

    def generate(self, prompt: str) -> str:

        # Company Agent
        if "estimated_employees" in prompt:
            return """
{
    "industry":"Technology",
    "company_size":"Enterprise",
    "estimated_employees":5000,
    "market":"Software",
    "headquarters":"San Francisco",
    "confidence":98
}
"""

        # Contact Agent
        if "email_quality" in prompt:
            return """
{
    "email_quality":78,
    "decision_maker_probability":62,
    "department":"Sales",
    "contact_type":"Individual",
    "confidence":91
}
"""

        # Intent Agent
        if "buying_intent" in prompt:
            return """
{
    "buying_intent":74,
    "urgency":"Medium",
    "pain_point_probability":69,
    "recommended_outreach":"Discovery Call",
    "confidence":88
}
"""

        return "{}"