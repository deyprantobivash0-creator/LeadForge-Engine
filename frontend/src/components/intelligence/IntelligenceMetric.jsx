function IntelligenceMetric({
  label,
  value = 0,
  tone = "purple",
}) {
  const safeValue = Math.max(
    0,
    Math.min(100, Number(value) || 0)
  );

  return (
    <div className="intelligence-metric">
      <div className="intelligence-metric-header">
        <span>{label}</span>

        <strong>{safeValue}%</strong>
      </div>

      <div className="intelligence-metric-track">
        <div
          className={`intelligence-metric-progress intelligence-metric-${tone}`}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}

export default IntelligenceMetric;