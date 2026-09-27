export default function PremiumCard({children}){

return(

<div
style={{

background:"rgba(255,255,255,.78)",

backdropFilter:"blur(18px)",

border:"1px solid rgba(255,255,255,.45)",

borderRadius:"28px",

padding:"24px",

boxShadow:
"0 14px 35px rgba(124,108,248,.08)",

transition:"all .3s ease"

}}
>

{children}

</div>

);

}