"""Application-owned Lead Brain qualification policy."""

from decimal import Decimal, ROUND_HALF_UP

from backend.schemas.lead_contract import LeadPriority


class LeadScorer:
    WEIGHTS = (40, 25, 35)

    @staticmethod
    def priority_for_score(score: int) -> LeadPriority:
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Lead score must be an integer from 0 to 100")
        if score >= 80:
            return LeadPriority.HOT
        if score >= 60:
            return LeadPriority.WARM
        return LeadPriority.COLD

    def score_components(self, company: int, contact: int, intent: int) -> tuple[int, LeadPriority]:
        components = (company, contact, intent)
        if any(type(value) is not int or not 0 <= value <= 100 for value in components):
            raise ValueError("Component scores must be integers from 0 to 100")
        weighted = sum(Decimal(value * weight) for value, weight in zip(components, self.WEIGHTS)) / Decimal(100)
        score = int(weighted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return score, self.priority_for_score(score)
