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