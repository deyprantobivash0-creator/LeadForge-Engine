from backend.graph.state import LeadState

from backend.agents.company_agent import CompanyAgent
from backend.agents.contact_agent import ContactAgent
from backend.agents.intent_agent import IntentAgent

from backend.decision.lead_scorer import LeadScorer


company_agent = CompanyAgent()
contact_agent = ContactAgent()
intent_agent = IntentAgent()

scorer = LeadScorer()


def company_node(state: LeadState):

    state["company_analysis"] = company_agent.analyze(
        state["company"]
    )

    return state


def contact_node(state: LeadState):

    state["contact_analysis"] = contact_agent.analyze(
        state["email"]
    )

    return state


def intent_node(state: LeadState):

    state["intent_analysis"] = intent_agent.analyze(
        state["company"],
        state["email"],
    )

    return state


def decision_node(state: LeadState):

    state["final_decision"] = scorer.score(
        state["company_analysis"],
        state["contact_analysis"],
        state["intent_analysis"],
    )

    return state