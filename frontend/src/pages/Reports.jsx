import PageHeader from "../components/common/PageHeader";
import GlassCard from "../components/common/GlassCard";

export default function Reports(){

return(

<div className="dashboard">

<PageHeader

title="Reports"

subtitle="Executive pipeline analytics."

/>

<div className="dashboard">

<PageHeader

title="Executive Reports"

subtitle="Pipeline analytics."

/>

<div className="workspace-grid">

<GlassCard>

<h3>Revenue Potential</h3>

<h1>$128,000</h1>

</GlassCard>

<GlassCard>

<h3>Conversion Trend</h3>

<p>

Chart coming next.

</p>

</GlassCard>

<GlassCard>

<h3>Monthly Growth</h3>

<p>

+24%

</p>

</GlassCard>

</div>

</div>

);

}