import { Inbox } from "lucide-react";

export default function EmptyState({
  title,
  subtitle,
}) {
  return (
    <div className="empty-state glass">

      <Inbox size={42}/>

      <h3>{title}</h3>

      <p>{subtitle}</p>

    </div>
  );
}