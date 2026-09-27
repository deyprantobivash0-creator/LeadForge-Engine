import { useEffect, useState } from "react";

import {
  X,
  Mail,
  Building2,
  Globe2,
  CalendarClock,
  Clock3,
  Sparkles,
  Target,
  CheckCircle2,
  AlertCircle,
  Save,
  FileText,
} from "lucide-react";

import PriorityBadge from "../dashboard/PriorityBadge";
import api from "../../services/api";
import { updateLeadLifecycle } from "../../services/leadService";

function LeadDetails({ leadId, onClose }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
const [saveSuccess, setSaveSuccess] = useState(false);

const [status, setStatus] = useState("New");
const [notes, setNotes] = useState("");
const [lastContacted, setLastContacted] = useState("");
const [nextFollowUp, setNextFollowUp] = useState("");

async function handleSaveLifecycle() {
  try {
    setSaving(true);
    setSaveSuccess(false);

    await updateLeadLifecycle(leadId, {
      status,
      notes,
      last_contacted: lastContacted || null,
      next_follow_up: nextFollowUp || null,
    });

    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2500);
  } catch (err) {
    console.error("Failed to update lead lifecycle:", err);
  } finally {
    setSaving(false);
  }
}

// Date input values (YYYY-MM-DD)
const formattedLastContactedInput = lead?.last_contacted
  ? new Date(lead.last_contacted).toISOString().split("T")[0]
  : "";

const formattedNextFollowUpInput = lead?.next_follow_up
  ? new Date(lead.next_follow_up).toISOString().split("T")[0]
  : "";

// Display values
const formattedLastContacted = lead?.last_contacted
  ? new Date(lead.last_contacted).toLocaleDateString()
  : "Never";

const formattedNextFollowUp = lead?.next_follow_up
  ? new Date(lead.next_follow_up).toLocaleDateString()
  : "Not scheduled";


  useEffect(() => {
    if (!leadId) return;

    async function loadLeadIntelligence() {
      try {
        setLoading(true);
        setError("");

        const response = await api.get(
          `/api/leads/${leadId}/intelligence`
        );

          const data = response.data;
        setLead(response.data);
      

setStatus(data.status || "New");
setNotes(data.notes || "");

setLastContacted(
  data.last_contacted
    ? data.last_contacted.slice(0, 10)
    : ""
);

setNextFollowUp(
  data.next_follow_up
    ? data.next_follow_up.slice(0, 10)
    : ""
);
      } catch (err) {
        console.error("Failed to load lead intelligence:", err);
        setError("Unable to load lead intelligence.");
      } finally {
        setLoading(false);
      }
    }

    loadLeadIntelligence();
  }, [leadId]);

  if (!leadId) {
    return null;
  }

  const analysis = lead?.analysis || {};
  const score = Number(
    analysis.lead_score ?? lead?.lead_score ?? 0
  );

  const priority =
    analysis.priority ||
    lead?.priority ||
    "LOW";

  const displayStatus =
    lead?.status ||
    "New";

  const scoreLabel =
    score >= 80
      ? "Excellent"
      : score >= 60
      ? "Strong"
      : score >= 40
      ? "Moderate"
      : "Low";

    

  return (
    <div
      className="lead-details-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <aside
        className="lead-details-panel"
        onMouseDown={(event) => event.stopPropagation()}
      >
        {/* HEADER */}
        <div className="details-header">
          <div>
            <div className="section-eyebrow">
              LEAD INTELLIGENCE
            </div>

            <h2>
              {lead?.company || "Lead Details"}
            </h2>

            {lead?.source && (
              <span className="details-source">
                {lead.source}
              </span>
            )}
          </div>

          <button
            type="button"
            className="details-close"
            onClick={onClose}
            aria-label="Close lead details"
          >
            <X size={20} />
          </button>
        </div>

        {/* LOADING */}
        {loading && (
          <div className="details-state">
            <div className="details-loader" />
            <p>Loading lead intelligence...</p>
          </div>
        )}

        {/* ERROR */}
        {!loading && error && (
          <div className="details-state details-error">
            <AlertCircle size={22} />
            <p>{error}</p>

            <button
              type="button"
              onClick={() => window.location.reload()}
            >
              Retry
            </button>
          </div>
        )}

        {/* CONTENT */}
        {!loading && !error && lead && (
          <div className="details-content">

            {/* CONTACT */}
            <div className="details-contact-card">
              <div className="lead-company-avatar">
                {(lead.company || "L").charAt(0).toUpperCase()}
              </div>

              <div className="contact-main">
                <strong>
                  {lead.company || "Unknown Company"}
                </strong>

                <div className="contact-email">
                  <Mail size={14} />
                  <span>
                    {lead.email || "No email available"}
                  </span>
                </div>
              </div>
            </div>

            {/* SCORE + PRIORITY */}
            <div className="details-metrics">

              <div className="metric-card score-card">
                <div className="metric-card-top">
                  <span>LEAD SCORE</span>
                  <Target size={17} />
                </div>

                <div className="score-value">
                  {score}
                  <small>/100</small>
                </div>

                <div className="score-bar">
                  <div
                    className="score-bar-fill"
                    style={{
                      width: `${Math.min(
                        Math.max(score, 0),
                        100
                      )}%`,
                    }}
                  />
                </div>

                <span className="score-label">
                  {scoreLabel}
                </span>
              </div>

              <div className="metric-card priority-card">
                <div className="metric-card-top">
                  <span>PRIORITY</span>
                  <Sparkles size={17} />
                </div>

                <div className="priority-value">
                  <PriorityBadge priority={priority} />
                </div>

                <span className="metric-subtext">
                  AI assessed intent
                </span>
              </div>
            </div>

            {/* LIFECYCLE */}
            <div className="details-section">
              <div className="details-section-heading">
                <span className="section-eyebrow">
                  LIFECYCLE
                </span>
              </div>

              <div className="lifecycle-row">
                <div className="lifecycle-icon">
                  <CheckCircle2 size={17} />
                </div>

                <div>
                  <span>Status</span>
                  <strong>{displayStatus}</strong>
                </div>
              </div>
            </div>

            {/* AI INTELLIGENCE */}
            <div className="intelligence-box">
              <div className="intelligence-heading">
                <div className="intelligence-icon">
                  <Sparkles size={17} />
                </div>

                <div>
                  <span className="section-eyebrow">
                    AI INTELLIGENCE
                  </span>
                  <h3>Lead Analysis</h3>
                </div>
              </div>

              {analysis.recommendation ? (
                <div className="recommendation-card">
                  <span>RECOMMENDATION</span>
                  <p>
                    {analysis.recommendation}
                  </p>
                </div>
              ) : (
                <div className="empty-intelligence">
                  <Sparkles size={18} />
                  <span>
                    No AI recommendation available yet.
                  </span>
                </div>
              )}

              <div className="intelligence-grid">
                {analysis.industry && (
                  <div className="intelligence-item">
                    <Building2 size={16} />
                    <div>
                      <span>Industry</span>
                      <strong>
                        {analysis.industry}
                      </strong>
                    </div>
                  </div>
                )}

                {analysis.company_size && (
                  <div className="intelligence-item">
                    <Globe2 size={16} />
                    <div>
                      <span>Company Size</span>
                      <strong>
                        {analysis.company_size}
                      </strong>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* LIFECYCLE CONTROL */}

<div className="lifecycle-editor">

  <div className="details-section-heading">
    <span className="section-eyebrow">
      LIFECYCLE CONTROL
    </span>

    <p>
      Update the current sales position.
    </p>
  </div>

  <div className="form-field">
    <label htmlFor="lead-status">
      STATUS
    </label>

    <select
      id="lead-status"
      value={status}
      onChange={(event) =>
        setStatus(event.target.value)
      }
    >
      <option value="New">
        New
      </option>

      <option value="Contacted">
        Contacted
      </option>

      <option value="Qualified">
        Qualified
      </option>

      <option value="In Progress">
        In Progress
      </option>

      <option value="Converted">
        Converted
      </option>
    </select>
  </div>

  <div className="activity-edit-grid">

    <div className="form-field">
      <label htmlFor="last-contacted">
        LAST CONTACTED
      </label>

      <div className="input-icon">
        <Clock3 size={15} />

             <input
               id="last-contacted"
               type="date"
               value={lastContacted}
               onChange={(event) =>
               setLastContacted(event.target.value)
               }
              />
      </div>
    </div>

    <div className="form-field">
      <label htmlFor="next-follow-up">
        NEXT FOLLOW-UP
      </label>

      <div className="input-icon">
        <CalendarClock size={15} />

        <input
          id="next-follow-up"
          type="date"
          value={formattedNextFollowUpInput}
          onChange={(event) =>
            setNextFollowUp(
              event.target.value
            )
          }
        />
      </div>
    </div>

  </div>

  <div className="form-field">
    <label htmlFor="lead-notes">
      INTERNAL NOTES
    </label>

    <div className="textarea-wrapper">
      <FileText size={15} />

      <textarea
        id="lead-notes"
        placeholder="Add notes about this lead..."
        value={notes}
        onChange={(event) =>
          setNotes(event.target.value)
        }
        rows={4}
      />
    </div>
  </div>

  <button
    type="button"
    className="save-lifecycle-button"
    onClick={handleSaveLifecycle}
    disabled={saving}
  >
    {saving ? (
      <>
        <span className="button-spinner" />
        Saving...
      </>
    ) : (
      <>
        <Save size={16} />
        Save Changes
      </>
    )}
  </button>

  {saveSuccess && (
    <div className="save-success">
      <CheckCircle2 size={15} />
      Lead lifecycle updated successfully.
    </div>
  )}

</div>

            {/* FOLLOW-UP */}
            <div className="details-section">
              <div className="details-section-heading">
                <span className="section-eyebrow">
                  ACTIVITY
                </span>
              </div>

              <div className="activity-grid">

                <div className="activity-item">
                  <Clock3 size={17} />

                  <div>
                    <span>Last Contacted</span>
                    <strong>
                      {lead.last_contacted
                        ? new Date(
                            lead.last_contacted
                          ).toLocaleDateString()
                        : "Not contacted"}
                    </strong>
                  </div>
                </div>

                <div className="activity-item">
                  <CalendarClock size={17} />

                  <div>
                    <span>Next Follow-up</span>
                    <strong>
                      {lead.next_follow_up
                        ? new Date(
                            lead.next_follow_up
                          ).toLocaleDateString()
                        : "Not scheduled"}
                    </strong>
                  </div>
                </div>

              </div>
            </div>

            {/* LEAD META */}
            <div className="details-section">
              <div className="details-section-heading">
                <span className="section-eyebrow">
                  LEAD INFORMATION
                </span>
              </div>

              <div className="meta-list">

                <div>
                  <span>Source</span>
                  <strong>
                    {lead.source || "Unknown"}
                  </strong>
                </div>

                <div>
                  <span>Lead ID</span>
                  <strong>
                    #{lead.id}
                  </strong>
                </div>

              </div>
            </div>

          </div>
        )}
      </aside>
    </div>
  );
}

export default LeadDetails;
