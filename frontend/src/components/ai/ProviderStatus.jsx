import PremiumCard from "../ui/PremiumCard";

export default function ProviderStatus({
  provider = "Mock"
}) {
  return (
    <PremiumCard>

      <div className="provider-card">

        <h3>AI Provider</h3>

        <div className="provider-status">

          <span className="provider-dot"></span>

          {provider}

        </div>

        <small>Real-time AI engine status</small>

      </div>

    </PremiumCard>
  );
}