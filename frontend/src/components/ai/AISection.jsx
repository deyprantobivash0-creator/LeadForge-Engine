import ScoreRing from "./ScoreRing";
import ProviderStatus from "./ProviderStatus";
import RevenueCard from "./RevenueCard";
import TimelineCard from "./TimelineCard";
import InsightCard from "./InsightCard";

export default function AISection() {
  return (
    <div className="ai-grid">

      <ScoreRing score={92}/>

      <RevenueCard amount="$48,000"/>

      <ProviderStatus provider="Mock"/>

      <TimelineCard/>

      <InsightCard/>

    </div>
  );
}
