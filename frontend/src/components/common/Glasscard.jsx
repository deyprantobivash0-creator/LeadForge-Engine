/** @param {{children?:import('react').ReactNode,className?:string}} props */
export default function GlassCard({
  children,
  className = "",
}) {
  return (
    <div className={`glass ${className}`}>
      {children}
    </div>
  );
}
