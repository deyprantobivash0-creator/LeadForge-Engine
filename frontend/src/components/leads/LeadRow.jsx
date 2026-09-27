import PriorityBadge from "../dashboard/PriorityBadge";

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getScoreClass(score) {
  if (score >= 80) {
    return "score-high";
  }

  if (score >= 50) {
    return "score-medium";
  }

  return "score-low";
}

function LeadRow({ lead, onSelect }) {
  const score =
    typeof lead.lead_score === "number"
      ? lead.lead_score
      : null;

  return (
    <tr
      className="lead-row"
      onClick={() => onSelect?.(lead.id)}
    >

      {/* COMPANY */}

      <td>

        <div className="lead-company">

          <div className="company-avatar">
            {lead.company?.charAt(0)?.toUpperCase() || "L"}
          </div>

          <div className="company-info">

            <strong>
              {lead.company || "Unknown company"}
            </strong>

            <span>
              Lead #{lead.id}
            </span>

          </div>

        </div>

      </td>


      {/* CONTACT */}

      <td>

        <div className="lead-contact">
          {lead.email || "—"}
        </div>

      </td>


      {/* SOURCE */}

      <td>

        <span className="source-badge">
          {lead.source || "Unknown"}
        </span>

      </td>


      {/* SCORE */}

      <td>

        <div className="score-cell">

          <span
            className={`lead-score ${
              score !== null
                ? getScoreClass(score)
                : ""
            }`}
          >
            {score !== null ? score : "—"}
          </span>

          {score !== null && (
            <div className="score-bar">
              <span
                style={{
                  width: `${Math.min(
                    Math.max(score, 0),
                    100
                  )}%`,
                }}
              />
            </div>
          )}

        </div>

      </td>


      {/* PRIORITY */}

      <td>

        {lead.priority ? (
          <PriorityBadge
            priority={lead.priority}
          />
        ) : (
          <span className="muted-value">
            —
          </span>
        )}

      </td>


      {/* STATUS */}

      <td>

        <span
          className={`lead-status ${
            lead.status
              ? lead.status
                  .toLowerCase()
                  .replace(/\s+/g, "-")
              : ""
          }`}
        >
          {lead.status || "Unknown"}
        </span>

      </td>


      {/* FOLLOW-UP */}

      <td>

        <span className="follow-up-date">
          {formatDate(lead.next_follow_up)}
        </span>

      </td>

    </tr>
  );
}

export default LeadRow;