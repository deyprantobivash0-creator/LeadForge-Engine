from backend.agents.contact_agent import ContactAgent

agent = ContactAgent()

result = agent.analyze("sales@tesla.com")

print(result)