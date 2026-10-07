from backend.agents.intent_agent import IntentAgent

agent = IntentAgent()

result = agent.analyze(
    "Tesla",
    "sales@tesla.com"
)

print(result)