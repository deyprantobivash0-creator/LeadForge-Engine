const dimensions = [
  { key: "company", label: "Company Fit" },
  { key: "contact", label: "Contact Quality" },
  { key: "intent", label: "Buying Intent" },
];

const scoreOrNull = (value) => Number.isInteger(value) && value >= 0 && value <= 100 ? value : null;

export function presentAnalysis(analysis) {
  if (!analysis) return null;
  const result = analysis.result?.schema_version === 1 ? analysis.result : null;
  const decision = result?.final_decision;
  return {
    id: analysis.id,
    score: scoreOrNull(analysis.lead_score),
    priority: ["Hot", "Warm", "Cold"].includes(analysis.priority) ? analysis.priority : null,
    createdAt: analysis.created_at || null,
    recommendedAction: typeof decision?.recommended_action === "string" ? decision.recommended_action : null,
    dimensions: dimensions.map(({ key, label }) => {
      const stage = result?.[key];
      return {
        key,
        label,
        score: scoreOrNull(stage?.score),
        summary: typeof stage?.summary === "string" ? stage.summary : null,
        evidence: Array.isArray(stage?.evidence) ? stage.evidence.filter((item) =>
          item && ["lead_data", "derived"].includes(item.source) &&
          typeof item.field === "string" && typeof item.value === "string" &&
          typeof item.reasoning === "string"
        ) : [],
      };
    }),
  };
}

export function formatAnalysisDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Unavailable" : `${date.toLocaleString(undefined, { timeZone: "UTC" })} UTC`;
}
