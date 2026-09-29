export default function PremiumCard({
children,
className=""
}){

return(

<div className={`glass-card ${className}`}>

{children}

</div>

);

}