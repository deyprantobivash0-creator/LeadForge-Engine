import LeadRow from "./LeadRow";

function LeadTable({ leads, onSelectLead }) {
  return (
    <div className="lead-table-card">

      <div className="lead-table-header">

        <div>
          <span className="section-eyebrow">
            PIPELINE
          </span>

          <h2>Lead Directory</h2>
        </div>

        <span className="lead-table-total">
          {leads.length} records
        </span>

      </div>


      <div className="lead-table-scroll">

        <table className="lead-table">

          <thead>
            <tr>
              <th>COMPANY</th>
              <th>CONTACT</th>
              <th>SOURCE</th>
              <th>SCORE</th>
              <th>PRIORITY</th>
              <th>STATUS</th>
              <th>FOLLOW-UP</th>
            </tr>
          </thead>

          <tbody>

            {leads.map((lead) => (
              <LeadRow
                key={lead.id}
                lead={lead}
                onSelect={onSelectLead}
              />
            ))}

          </tbody>

        </table>

      </div>

    </div>
  );
}

export default LeadTable;