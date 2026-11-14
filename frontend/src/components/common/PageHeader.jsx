/** @param {{title:import('react').ReactNode,subtitle?:import('react').ReactNode,action?:import('react').ReactNode}} props */
export default function PageHeader({
  title,
  subtitle,
  action,
}) {
  return (
    <div className="page-header glass">

      <div>

        <h1>{title}</h1>

        <p>{subtitle}</p>

      </div>

      {action}

    </div>
  );
}
