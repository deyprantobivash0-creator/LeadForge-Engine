export default function NavItem({
  icon,
  label,
  active = false,
  onClick,
}) {
  return (
    <button
      onClick={onClick}
      type="button"
      aria-current={active ? "page" : undefined}
      className={`nav-item ${active ? "active" : ""}`}
    >
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}
