from langgraph.graph import StateGraph, END

from backend.graph.state import LeadState
from backend.graph.nodes import (
    company_node,
    contact_node,
    intent_node,
    decision_node,
)


builder = StateGraph(LeadState)

builder.add_node("company", company_node)
builder.add_node("contact", contact_node)
builder.add_node("intent", intent_node)
builder.add_node("decision", decision_node)

builder.set_entry_point("company")

builder.add_edge("company", "contact")
builder.add_edge("contact", "intent")
builder.add_edge("intent", "decision")
builder.add_edge("decision", END)

graph = builder.compile()