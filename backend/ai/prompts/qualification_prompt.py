def build_prompt(company: str, email: str):

    return f"""
You are a B2B Lead Qualification AI.

Return ONLY JSON.

Company:
{company}

Email:
{email}

Return:

{{
  "industry":"",
  "company_size":"",
  "lead_score":0,
  "priority":"",
  "recommendation":""
}}

No markdown.
JSON only.
"""