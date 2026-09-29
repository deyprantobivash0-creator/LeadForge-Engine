import { Upload } from "lucide-react";

import PageHeader from "../components/common/PageHeader";
import GlassCard from "../components/common/GlassCard";

export default function Imports(){

return(

<div className="dashboard">

<PageHeader

title="Import Leads"

subtitle="CSV and Excel ingestion."

/>

<GlassCard>

<div className="upload-zone">

<Upload size={54}/>

<h3>Drop your CSV here</h3>

<p>Drag & drop or click to upload.</p>

<button className="btn-primary">

Upload File

</button>

</div>

</GlassCard>

</div>

);

}