def build_company_prompt(company: str) -> str:
    return f"""
You are a company research AI.

Analyze the company below.

Company:
{company}

Return ONLY valid JSON.

Format:

{{
  "industry": "",
  "company_size": "",
  "estimated_employees": 0,
  "market": "",
  "headquarters": "",
  "confidence": 0
}}

Do not include markdown.
Return JSON only.
"""