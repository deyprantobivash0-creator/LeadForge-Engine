import { Sparkles } from "lucide-react";

function OpportunityScore({
  score = 0,
  priority = null,
}) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));

  const getTone = () => {
    if (safeScore >= 80) return "purple";
    if (safeScore >= 60) return "blue";
    return "yellow";
  };

  const tone = getTone();

  return (
    <div className={`opportunity-score opportunity-score-${tone}`}>
      <div className="opportunity-score-header">
        <div>
          <span className="intelligence-eyebrow">
            AI OPPORTUNITY SCORE
          </span>

          <div className="opportunity-score-value">
            {safeScore}
          </div>
        </div>

        <div className="opportunity-score-icon">
          <Sparkles size={20} />
        </div>
      </div>

      <div className="opportunity-score-track">
        <div
          className="opportunity-score-progress"
          style={{ width: `${safeScore}%` }}
        />
      </div>

      <div className="opportunity-score-footer">
        <span>Lead Priority</span>

        <strong>{priority ?? "Unassigned"}</strong>
      </div>
    </div>
  );
}

export default OpportunityScore;
