import PriorityBadge from "./PriorityBadge";

function RecentLeads({ leads = [] }) {
  return (
    <div className="recent-leads-card">
      <div className="section-heading">
        <div>
          <div className="section-eyebrow">
            PIPELINE ACTIVITY
          </div>

          <h2>Recent Analyses</h2>
        </div>

        <span className="section-count">
          {leads.length} records
        </span>
      </div>

      <div className="table-wrapper">
        <table className="lead-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Score</th>
              <th>Priority</th>
              <th>Status</th>
            </tr>
          </thead>

          <tbody>
            {leads.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty-state">
                  No recent analyses available.
                </td>
              </tr>
            ) : (
              leads.map((lead, index) => (
                <tr key={lead.id || index}>
                  <td>
                    <div className="company-cell">
                      <div className="company-avatar">
                        {String(
                          lead.company || "?"
                        )
                          .charAt(0)
                          .toUpperCase()}
                      </div>

                      <span>
                        {lead.company || "Unknown"}
                      </span>
                    </div>
                  </td>

                  <td>
                    <span className="score-value">
                      {lead.lead_score ?? 0}
                    </span>
                  </td>

                  <td>
                    <PriorityBadge
                      priority={lead.priority}
                    />
                  </td>

                  <td>
                    <span className="status-text">
                      {lead.status || "Analyzed"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default RecentLeads;