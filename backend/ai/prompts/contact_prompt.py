def build_contact_prompt(email: str) -> str:
    return f"""
You are an expert B2B contact qualification AI.

Analyze this business email.

Email:
{email}

Return ONLY valid JSON.

Format:

{{
  "email_quality": 0,
  "decision_maker_probability": 0,
  "department": "",
  "contact_type": "",
  "confidence": 0
}}

Definitions:
- email_quality: 0-100 score based on usefulness for B2B outreach.
- decision_maker_probability: 0-100 estimate that this email belongs to a decision-maker.
- department: Most likely business function (Sales, Procurement, HR, IT, Executive, Unknown).
- contact_type: One of "Individual", "Department", "Generic", or "Unknown".
- confidence: Confidence in the analysis (0-100).

Return JSON only.
Do not use markdown.
"""