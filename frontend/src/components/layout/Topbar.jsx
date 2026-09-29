import { Search, Bell } from "lucide-react";

export default function TopBar() {
 return (

<header className="topbar glass">

<div className="topbar-left">

<div className="search-box">

<Search size={18}/>

<input

placeholder="Search leads, companies, contacts..."

type="text"

/>

</div>

</div>

<div className="topbar-right">

<button className="icon-button">

<Bell size={20}/>

</button>

<button className="avatar-button">

P

</button>

</div>

</header>

);
}