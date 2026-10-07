import { ArrowUpRight, Sparkles } from "lucide-react";

function RecommendationCard({
  action = "Review this lead",
  reason = "",
}) {
  return (
    <div className="recommendation-card">
      <div className="recommendation-icon">
        <Sparkles size={19} />
      </div>

      <div className="recommendation-content">
        <span className="intelligence-eyebrow">
          NEXT BEST ACTION
        </span>

        <h3>{action}</h3>

        {reason && (
          <p>{reason}</p>
        )}

        <button
          type="button"
          className="recommendation-action"
        >
          Take Action
          <ArrowUpRight size={15} />
        </button>
      </div>
    </div>
  );
}

export default RecommendationCard;