export default function PremiumButton({

children,
onClick,
variant="primary"

}){

const styles={

primary:{
background:"#0F172A",
color:"#fff"
},

secondary:{
background:"#EAF4FF",
color:"#111827"
}

};

return(

<button

onClick={onClick}

style={{

...styles[variant],

border:"none",
padding:"12px 22px",
borderRadius:"14px",
cursor:"pointer",
fontWeight:600,
transition:"0.25s"

}}

>

{children}

</button>

);

}