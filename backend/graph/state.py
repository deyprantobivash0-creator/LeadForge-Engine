from typing import TypedDict


class LeadState(TypedDict):

    company: str

    email: str

    company_analysis: dict

    contact_analysis: dict

    intent_analysis: dict

    final_decision: dict