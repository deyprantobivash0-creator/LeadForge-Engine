"""The sole registered Lead Brain graph: three assessments, then app scoring."""

import asyncio
import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from backend.ai.providers.base import (
    AIProvider, ProviderMalformedOutput, ProviderTimeout, ProviderUnavailable,
)
from backend.ai.schemas.lead_brain import FinalDecision, LeadBrainResult, StageAssessment
from backend.core.config import settings
from backend.decision.lead_scorer import LeadScorer


class LeadBrainState(TypedDict, total=False):
    context: dict[str, str | None]
    company: StageAssessment
    contact: StageAssessment
    intent: StageAssessment
    result: LeadBrainResult


class LeadBrainWorkflow:
    def __init__(self, provider: AIProvider):
        self.provider = provider
        self.scorer = LeadScorer()
        builder = StateGraph(LeadBrainState)
        builder.add_node("company", self._company)
        builder.add_node("contact", self._contact)
        builder.add_node("intent", self._intent)
        builder.add_node("qualification", self._qualification)
        builder.set_entry_point("company")
        builder.add_edge("company", "contact")
        builder.add_edge("contact", "intent")
        builder.add_edge("intent", "qualification")
        builder.add_edge("qualification", END)
        self.graph = builder.compile()

    async def _assess(self, stage: str, context: dict[str, str | None]) -> StageAssessment:
        supplied = {key: value for key, value in context.items() if value is not None}
        prompt = (
            f"Assess only the {stage} dimension of this B2B Lead. "
            "Use only the supplied Lead fields. No web research or external facts. "
            "Unknown is not negative evidence: use score 0 when there is insufficient "
            "support, and say so. Return concise user-facing reasoning, not hidden reasoning. "
            "Do not invent revenue, headcount, roles, visits, events, or intent signals. "
            "Return a JSON object with integer score 0-100, summary, and evidence list. "
            "Each evidence item has source lead_data or derived, field company/email/source/industry, "
            "value and reasoning. For lead_data, value must exactly equal the supplied field; "
            "for derived, explicitly label an inference and explain which supplied field supports it. "
            "Do not provide final lead score or priority.\n"
            f"LEAD_CONTEXT_JSON={json.dumps(supplied, ensure_ascii=False)}"
        )
        for attempt in range(settings.AI_MAX_ATTEMPTS):
            try:
                raw = await asyncio.wait_for(
                    self.provider.generate_structured(prompt, StageAssessment),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
                assessment = StageAssessment.model_validate(raw)
                if assessment.score > 0 and not assessment.evidence:
                    raise ProviderMalformedOutput("Positive assessment requires evidence")
                for evidence in assessment.evidence:
                    if evidence.field not in supplied:
                        raise ProviderMalformedOutput("Evidence references absent Lead data")
                    if evidence.source == "lead_data" and evidence.value != supplied[evidence.field]:
                        raise ProviderMalformedOutput("Evidence does not match supplied Lead data")
                return assessment
            except asyncio.TimeoutError as exc:
                error = ProviderTimeout("Provider timed out")
                if attempt + 1 == settings.AI_MAX_ATTEMPTS:
                    raise error from exc
            except (ProviderTimeout, ProviderUnavailable):
                if attempt + 1 == settings.AI_MAX_ATTEMPTS:
                    raise
            except ValidationError as exc:
                raise ProviderMalformedOutput("Provider output failed validation") from exc
        raise ProviderUnavailable("Provider retries exhausted")

    async def _company(self, state: LeadBrainState):
        return {"company": await self._assess("company fit", state["context"])}

    async def _contact(self, state: LeadBrainState):
        return {"contact": await self._assess("contact quality", state["context"])}

    async def _intent(self, state: LeadBrainState):
        return {"intent": await self._assess("buying intent", state["context"])}

    async def _qualification(self, state: LeadBrainState):
        score, priority = self.scorer.score_components(
            state["company"].score, state["contact"].score, state["intent"].score,
        )
        action = {
            "Hot": "Review evidence and arrange a discovery call.",
            "Warm": "Review evidence and send a relevant introduction.",
            "Cold": "Verify lead details before outreach.",
        }[priority.value]
        result = LeadBrainResult(
            company=state["company"], contact=state["contact"], intent=state["intent"],
            final_decision=FinalDecision(
                lead_score=score, priority=priority.value, recommended_action=action,
            ),
        )
        return {"result": result}

    async def run(self, context: dict[str, str | None]) -> LeadBrainResult:
        state = await self.graph.ainvoke({"context": context})
        return LeadBrainResult.model_validate(state["result"])
