import PremiumCard from "../ui/PremiumCard";

export default function KpiCard({

title,
value,
icon,
color="#7C6CF8"

}){

return(

<PremiumCard>

<div
style={{

display:"flex",
justifyContent:"space-between",
alignItems:"center"

}}
>

<div>

<p
style={{

fontSize:13,

letterSpacing:".08em",

textTransform:"uppercase",

color:"#64748B"

}}
>

{title}

</p>

<h2
style={{

fontSize:34,

marginTop:10,

color:"#1E293B"

}}
>

{value}

</h2>

</div>

<div
style={{

width:56,
height:56,

display:"flex",
justifyContent:"center",
alignItems:"center",

borderRadius:"18px",

background:`${color}20`,

color

}}
>

{icon}

</div>

</div>

</PremiumCard>

);

}