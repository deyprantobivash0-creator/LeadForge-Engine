import PremiumCard from "../ui/PremiumCard";

export default function KpiCard({

title,
value,
icon,
color="#7C6CF8"

}){

return(

<PremiumCard>
<div className=" ,glass-card kpi-card">

<div>

<p className="kpi-label">

{title}

</p>

<h2 className="kpi-value">

{value}

</h2>

</div>

<div
className="kpi-icon"

style={{

background:
`linear-gradient(135deg,${color}44,${color}22)`

}}
>

{icon}

</div>

</div>

</PremiumCard>

);

}