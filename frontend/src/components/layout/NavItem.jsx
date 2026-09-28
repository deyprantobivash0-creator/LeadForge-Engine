export default function NavItem({
  icon,
  label,
  active = false,
  onClick,
}) {
  return (
    <button
      onClick={onClick}
      className={`nav-item ${active ? "active" : ""}`}
    >
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}