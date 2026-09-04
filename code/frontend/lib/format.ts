export const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
export const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });
export function text(value: unknown, fallback = "Not available") { return value === null || value === undefined || value === "" ? fallback : String(value); }
export function boolLabel(value: unknown) { return value === true || String(value).toLowerCase() === "true" ? "Yes" : "No"; }
