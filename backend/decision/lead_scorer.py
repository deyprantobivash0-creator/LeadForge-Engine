class LeadScorer:

    def score(
        self,
        company_analysis: dict,
        contact_analysis: dict,
        intent_analysis: dict,
    ):

        score = 0
        reasons = []

        # -----------------------------
        # Company Score (40 points)
        # -----------------------------
        company_size = company_analysis.get("company_size", "").lower()

        if "enterprise" in company_size:
            score += 40
            reasons.append("Enterprise company")

        elif "mid" in company_size:
            score += 25
            reasons.append("Mid-sized company")

        else:
            score += 15
            reasons.append("Small company")

        # -----------------------------
        # Contact Score (25 points)
        # -----------------------------
        email_quality = contact_analysis.get("email_quality", 0)

        score += round(email_quality * 0.25)

        if email_quality >= 70:
            reasons.append("High-quality business contact")

        # -----------------------------
        # Intent Score (35 points)
        # -----------------------------
        buying_intent = intent_analysis.get("buying_intent", 0)

        score += round(buying_intent * 0.35)

        if buying_intent >= 70:
            reasons.append("Strong buying intent")

        # -----------------------------
        # Cap Score
        # -----------------------------
        score = min(score, 100)

        # -----------------------------
        # Priority
        # -----------------------------
        if score >= 80:
            priority = "Hot"
            action = "Schedule Discovery Call"

        elif score >= 60:
            priority = "Warm"
            action = "Start Email Sequence"

        else:
            priority = "Cold"
            action = "Research Further"

        return {
            "lead_score": score,
            "priority": priority,
            "recommended_action": action,
            "reasoning": reasons,
        }