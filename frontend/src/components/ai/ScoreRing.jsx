import PremiumCard from "../ui/PremiumCard";

export default function ScoreRing({ score = 92 }) {
  const angle = score * 3.6;

  return (
    <PremiumCard>
      <div className="score-ring-card">

        <h3>AI Opportunity Score</h3>

        <div
          className="score-ring"
          style={{
            background: `conic-gradient(#7C6CF8 ${angle}deg,#E8EAF5 ${angle}deg)`
          }}
        >
          <div className="score-ring-inner">
            <strong>{score}%</strong>
            <span>Ready</span>
          </div>
        </div>

      </div>
    </PremiumCard>
  );
}