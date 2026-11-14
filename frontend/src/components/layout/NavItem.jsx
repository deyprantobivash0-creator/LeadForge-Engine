/**
 * @param {{
 *   icon: import('react').ReactNode,
 *   label: string,
 *   active?: boolean,
 *   onClick?: (event: import('react').MouseEvent<HTMLButtonElement>) => void | Promise<void>
 * }} props
 */
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
