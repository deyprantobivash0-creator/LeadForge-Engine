import {
  Users,
  Flame,
  Target,
  TrendingUp,
} from "lucide-react";

const icons = {
  total: Users,
  hot: Flame,
  qualified: Target,
  score: TrendingUp,
};

function StatCard({
  label,
  value,
  description,
  type = "total",
}) {
  const Icon = icons[type] || Users;

  return (
    <div className="stat-card">
      <div className="stat-card-top">
        <div className="stat-icon">
          <Icon size={18} />
        </div>

        <span className="stat-label">
          {label}
        </span>
      </div>

      <div className="stat-value">
        {value}
      </div>

      {description && (
        <div className="stat-description">
          {description}
        </div>
      )}
    </div>
  );
}

export default StatCard;