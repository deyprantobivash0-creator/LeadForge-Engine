function PriorityBadge({ priority }) {
  const normalized =
    String(priority || "Unknown").toLowerCase();

  return (
    <span
      className={`priority-badge priority-${normalized}`}
    >
      <span className="priority-dot"></span>
      {priority || "Unknown"}
    </span>
  );
}

export default PriorityBadge;