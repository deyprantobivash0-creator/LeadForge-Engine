from pprint import pprint

from backend.workflows.lead_workflow import LeadWorkflow

workflow = LeadWorkflow()

report = workflow.run(
    company="Tesla",
    email="sales@tesla.com"
)

pprint(report)