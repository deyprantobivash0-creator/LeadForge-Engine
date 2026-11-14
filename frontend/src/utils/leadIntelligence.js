/**
 * @typedef {'company'|'contact'|'intent'} DimensionKey
 * @typedef {{source:'lead_data'|'derived',field:string,value:string,reasoning:string}} PresentedEvidence
 * @typedef {{key:DimensionKey,label:string,score:number|null,summary:string|null,evidence:PresentedEvidence[]}} PresentedDimension
 * @typedef {{id:number,score:number|null,priority:import('../types/api').LeadPriority|null,createdAt:string|null,recommendedAction:string|null,dimensions:PresentedDimension[]}} PresentedAnalysis
 * @typedef {Pick<import('../types/api').Analysis,'id'> & {lead_score?:unknown,priority?:unknown,created_at?:string|null,result?:unknown}} AnalysisPresentationInput
 */
/** @type {{key:DimensionKey,label:string}[]} */
const dimensions = [
  { key: "company", label: "Company Fit" },
  { key: "contact", label: "Contact Quality" },
  { key: "intent", label: "Buying Intent" },
];

/** @param {unknown} value @returns {number|null} */
const scoreOrNull = (value) => typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 100 ? value : null;

/** @param {unknown} value @returns {value is Record<string,unknown>} */
function isPropertyContainer(value) {
  return value !== null && (typeof value === "object" || typeof value === "function");
}

/** @param {unknown} value @returns {value is import('../types/api').LeadPriority} */
function isPriority(value) {
  return value === "Hot" || value === "Warm" || value === "Cold";
}

/** @param {unknown} item @returns {item is PresentedEvidence} */
function isEvidence(item) {
  return isPropertyContainer(item) && (item.source === "lead_data" || item.source === "derived") &&
    typeof item.field === "string" && typeof item.value === "string" && typeof item.reasoning === "string";
}

/** @param {AnalysisPresentationInput|null|undefined} analysis @returns {PresentedAnalysis|null} */
export function presentAnalysis(analysis) {
  if (!analysis) return null;
  const result = isPropertyContainer(analysis.result) && analysis.result.schema_version === 1 ? analysis.result : null;
  const decision = result?.final_decision;
  return {
    id: analysis.id,
    score: scoreOrNull(analysis.lead_score),
    priority: isPriority(analysis.priority) ? analysis.priority : null,
    createdAt: analysis.created_at || null,
    recommendedAction: isPropertyContainer(decision) && typeof decision.recommended_action === "string" ? decision.recommended_action : null,
    dimensions: dimensions.map(({ key, label }) => {
      const rawStage = result?.[key];
      const stage = isPropertyContainer(rawStage) ? rawStage : null;
      return {
        key,
        label,
        score: scoreOrNull(stage?.score),
        summary: typeof stage?.summary === "string" ? stage.summary : null,
        evidence: Array.isArray(stage?.evidence) ? stage.evidence.filter(isEvidence) : [],
      };
    }),
  };
}

/** @param {string|null|undefined} value @returns {string} */
export function formatAnalysisDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Unavailable" : `${date.toLocaleString(undefined, { timeZone: "UTC" })} UTC`;
}
