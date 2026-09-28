import PremiumCard from "../ui/PremiumCard";

export default function RevenueCard({
  amount = "$48,000"
}) {
  return (
    <PremiumCard>

      <div className="revenue-card">

        <h3>Revenue Potential</h3>

        <h1>{amount}</h1>

        <p>Estimated pipeline value</p>

      </div>

    </PremiumCard>
  );
}