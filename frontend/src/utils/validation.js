export function leadFields({ company, email, source }) {
  const errors = {};
  if (!company.trim()) errors.company = "Enter a company name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) errors.email = "Enter a valid contact email.";
  if (!source.trim()) errors.source = "Enter where this lead came from.";
  return errors;
}

export function apiFieldErrors(failure) {
  const errors = {};
  for (const detail of Array.isArray(failure.details) ? failure.details : []) {
    const field = detail.loc?.at(-1);
    if (["company", "email", "source"].includes(field)) errors[field] = `Check the ${field === "email" ? "contact email" : field} value and try again.`;
  }
  return errors;
}

export function validReportRange(start, end) {
  const parse = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
    const stamp = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === value ? stamp : NaN;
  };
  const first = parse(start), last = parse(end);
  return Number.isFinite(first) && Number.isFinite(last) && last >= first && (last - first) / 86400000 < 365;
}
