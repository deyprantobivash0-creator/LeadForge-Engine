import PageHeader from "../components/common/PageHeader";
import AISection from "../components/ai/AISection";

export default function AIIntelligence(){

return(

<div className="dashboard">

<PageHeader

title="AI Intelligence"

subtitle="Live insights from LeadForge AI."

/>

<div className="workspace-grid">

<GlassCard>

<h3>Lead Brain</h3>

<p>

3 companies are ready for outreach.

</p>

</GlassCard>

<GlassCard>

<h3>Provider</h3>

<StatusBadge type="sage">

Gemini Active

</StatusBadge>

</GlassCard>

<GlassCard>

<h3>Confidence</h3>

<h1>92%</h1>

</GlassCard>

<GlassCard>

<h3>Next Best Action</h3>

<p>

Send proposal to Stripe.

</p>

</GlassCard>

</div>

</div>
);

}