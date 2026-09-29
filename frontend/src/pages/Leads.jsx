import PageHeader from "../components/common/PageHeader";
import GlassCard from "../components/common/GlassCard";
import StatusBadge from "../components/common/StatusBadge";

export default function Leads(){

const leads=[

{
company:"OpenAI",
score:95,
priority:"High"
},

{
company:"Stripe",
score:88,
priority:"Medium"
},

{
company:"Canva",
score:91,
priority:"High"
}

];

return(

<div className="dashboard">

<PageHeader

title="Lead Workspace"

subtitle="Manage opportunities powered by AI."

action={<button className="btn-primary">+ New Lead</button>}

/>

<div className="glass table-glass">

<table>

<thead>

<tr>

<th>Company</th>

<th>Industry</th>

<th>AI Score</th>

<th>Status</th>

<th>Priority</th>

</tr>

</thead>

<tbody>

{leads.map((lead)=>(

<tr key={lead.company}>

<td>{lead.company}</td>

<td>{lead.industry}</td>

<td>

<div className="score-ring">

{lead.score}

</div>

</td>

<td>

<StatusBadge type="blue">

{lead.status}

</StatusBadge>

</td>

<td>

<StatusBadge

type={

lead.priority==="High"

? "purple"

: "sage"

}

>

{lead.priority}

</StatusBadge>

</td>

</tr>

))}

</tbody>

</table>

</div>

</div>

);

}