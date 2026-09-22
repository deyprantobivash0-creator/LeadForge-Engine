from backend.agents.company_agent import CompanyAgent
from backend.agents.contact_agent import ContactAgent
from backend.agents.intent_agent import IntentAgent
from backend.decision.lead_scorer import LeadScorer

class LeadWorkflow:

    def __init__(self):

        self.company_agent = CompanyAgent()
        self.contact_agent = ContactAgent()
        self.intent_agent = IntentAgent()
        self.scorer = LeadScorer()

    def run(self, company: str, email: str):

        company_result = self.company_agent.analyze(company)

        contact_result = self.contact_agent.analyze(email)

        intent_result = self.intent_agent.analyze(
            company,
            email,
        )

        decision = self.scorer.score(
            company_result,
            contact_result,
            intent_result,
        )

        return {
            "company_analysis": company_result,

    "contact_analysis": contact_result,

    "intent_analysis": intent_result,

    "final_decision": decision,

     }        