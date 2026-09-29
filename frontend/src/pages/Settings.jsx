import PageHeader from "../components/common/PageHeader";
import GlassCard from "../components/common/GlassCard";

export default function Settings(){

return(

<div className="dashboard">

<PageHeader

title="Settings"

subtitle="Configure LeadForge."

/>

<GlassCard>

<div className="settings-grid">

<label>

AI Provider

<select>

<option>Mock</option>

<option>Gemini</option>

<option>Ollama</option>

<option>DeepSeek</option>

</select>

</label>

<label>

Theme

<select>

<option>Aurora Dark</option>

</select>

</label>

</div>

</GlassCard>

</div>
);

}