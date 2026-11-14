/**
 * @typedef {'company'|'email'|'source'} LeadField
 * @typedef {Partial<Record<LeadField,string>>} LeadFieldErrors
 */

/** @param {unknown} value @returns {value is Record<string,unknown>} */
function isPropertyContainer(value) {
  return value !== null && (typeof value === "object" || typeof value === "function");
}

/** @param {unknown} value @returns {value is LeadField} */
function isLeadField(value) {
  return value === "company" || value === "email" || value === "source";
}

/** @param {import('../types/api').LeadCreate} values @returns {LeadFieldErrors} */
export function leadFields({ company, email, source }) {
  /** @type {LeadFieldErrors} */
  const errors = {};
  if (!company.trim()) errors.company = "Enter a company name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) errors.email = "Enter a valid contact email.";
  if (!source.trim()) errors.source = "Enter where this lead came from.";
  return errors;
}

/** @param {unknown} failure @returns {LeadFieldErrors} */
export function apiFieldErrors(failure) {
  /** @type {LeadFieldErrors} */
  const errors = {};
  // Preserve the original property-access failure for absent error objects.
  if (failure === null || failure === undefined) throw new TypeError(`Cannot read properties of ${failure} (reading 'details')`);
  const rawDetails = isPropertyContainer(failure) ? failure.details : undefined;
  /** @type {unknown[]} */
  const details = Array.isArray(rawDetails) ? rawDetails : [];
  for (const detail of details) {
    if (detail === null || detail === undefined) throw new TypeError(`Cannot read properties of ${detail} (reading 'loc')`);
    const location = isPropertyContainer(detail) ? detail.loc : undefined;
    /** @type {unknown} */
    let field;
    if (location !== null && location !== undefined) {
      if (typeof location === "string" || Array.isArray(location)) field = location.at(-1);
      else {
        const at = isPropertyContainer(location) ? location.at : undefined;
        if (typeof at !== "function") throw new TypeError("detail.loc?.at is not a function");
        field = at.call(location, -1);
      }
    }
    if (isLeadField(field)) errors[field] = `Check the ${field === "email" ? "contact email" : field} value and try again.`;
  }
  return errors;
}

/** @param {string} start @param {string} end @returns {boolean} */
export function validReportRange(start, end) {
  /** @param {string} value @returns {number} */
  const parse = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
    const stamp = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === value ? stamp : NaN;
  };
  const first = parse(start), last = parse(end);
  return Number.isFinite(first) && Number.isFinite(last) && last >= first && (last - first) / 86400000 < 365;
}
