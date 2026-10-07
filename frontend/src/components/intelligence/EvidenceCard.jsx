import { ShieldCheck } from "lucide-react";

function EvidenceCard({
  title = "AI Analysis",
  description = "",
  confidence = null,
}) {
  return (
    <div className="evidence-card">
      <div className="evidence-card-icon">
        <ShieldCheck size={17} />
      </div>

      <div className="evidence-card-content">
        <span className="intelligence-eyebrow">
          {title}
        </span>

        <p>
          {description || "No supporting evidence available yet."}
        </p>

        {confidence !== null && (
          <div className="evidence-confidence">
            Confidence {Math.round(Number(confidence) * 100)}%
          </div>
        )}
      </div>
    </div>
  );
}

export default EvidenceCard;