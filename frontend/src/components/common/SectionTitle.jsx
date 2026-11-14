/** @param {{title:import('react').ReactNode,subtitle?:import('react').ReactNode}} props */
export default function SectionTitle({
  title,
  subtitle,
}) {
  return (
    <div className="section-title">

      <h2>{title}</h2>

      <p>{subtitle}</p>

    </div>
  );
}
