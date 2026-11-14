/** @param {{type?:string,children?:import('react').ReactNode}} props */
export default function StatusBadge({
  type = "purple",
  children,
}) {
  return (
    <span className={`badge-${type}`}>
      {children}
    </span>
  );
}
