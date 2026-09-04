import { inr, number } from "./format.ts";

export type Row = Record<string, unknown>;
export type DisplayState = "strong_issue" | "review" | "analytical" | "context" | "pass" | "not_applicable" | "insufficient";

export interface MetricMetadata {
  label: string;
  unit: "currency" | "percent" | "percentage_points" | "days" | "count" | "ratio" | "percent_per_30_days";
  description: string;
  interpretation: string;
}

export const PEER_METRICS: Record<string, MetricMetadata> = {
  days_since_last_payment_as_of: { label: "Time since latest payment", unit: "days", description: "Days between the latest released payment and the analytical snapshot.", interpretation: "A larger value means the latest payment was longer ago than for the comparison group." },
  estimate_to_recommended_ratio: { label: "Technical estimate vs recommended amount", unit: "ratio", description: "Technical estimate divided by the recommended amount.", interpretation: "Shows how the estimate compares with the original recommendation." },
  expected_minus_physical_gap_pct_as_of: { label: "Expected vs physical progress gap", unit: "percentage_points", description: "Expected progress minus reported physical progress.", interpretation: "A positive value indicates reported physical progress trails the recorded expectation." },
  expenditure_to_sanction_pct_as_of: { label: "Released payments as share of sanction", unit: "percent", description: "Released-payment total divided by the visible sanctioned amount.", interpretation: "Shows the share of the visible sanction represented by released payments." },
  financial_minus_physical_gap_pct_as_of: { label: "Financial vs physical progress gap", unit: "percentage_points", description: "Reported financial progress minus reported physical progress.", interpretation: "A positive value means financial progress is ahead of physical progress." },
  financial_overrun_pct_as_of: { label: "Amount above sanction", unit: "percent", description: "Released payments above the visible sanction as a percentage of sanction.", interpretation: "Positive values should be checked against any revised sanction or authorized variation." },
  largest_payment_share_as_of: { label: "Largest single payment share", unit: "ratio", description: "Largest released payment divided by total released payments.", interpretation: "Describes payment concentration without implying wrongdoing." },
  latest_financial_progress_pct_as_of: { label: "Latest reported financial progress", unit: "percent", description: "Financial progress in the latest progress report.", interpretation: "Compare with physical progress and the work stage." },
  latest_physical_progress_pct_as_of: { label: "Latest reported physical progress", unit: "percent", description: "Physical completion in the latest progress report.", interpretation: "Shows the most recently reported extent of physical completion." },
  max_physical_progress_drop_pct_as_of: { label: "Largest recorded physical progress decrease", unit: "percentage_points", description: "Largest drop between consecutive progress reports.", interpretation: "A non-zero decrease can require source-report reconciliation when governed evidence flags it." },
  overdue_days_as_of: { label: "Observed overdue days", unit: "days", description: "Days past expected completion for an unfinished work at the snapshot date.", interpretation: "This is an observed schedule condition, not a model probability." },
  physical_progress_decrease_count_as_of: { label: "Recorded physical progress decreases", unit: "count", description: "Number of decreases between consecutive physical-progress reports.", interpretation: "Indicates how often reported progress moved backward." },
  physical_progress_velocity_pct_per_30d: { label: "Physical progress pace", unit: "percent_per_30_days", description: "Recent physical progress change normalized to 30 days.", interpretation: "Shows pace relative to lifecycle-similar works." },
  recommended_amount_inr: { label: "Recommended amount", unit: "currency", description: "Amount recorded at recommendation.", interpretation: "Compare the work's recommendation with similar works." },
  released_payment_total_inr_as_of: { label: "Released payments", unit: "currency", description: "Total released payments visible at the snapshot date.", interpretation: "Compare with the visible sanction and lifecycle-similar works." },
  sanction_to_estimate_ratio: { label: "Sanction vs technical estimate", unit: "ratio", description: "Sanctioned amount divided by technical estimate.", interpretation: "Shows how the visible sanction compares with the technical estimate." },
  sanction_to_recommended_ratio: { label: "Sanction vs recommended amount", unit: "ratio", description: "Sanctioned amount divided by recommended amount.", interpretation: "Shows how the sanction compares with the recommendation." },
  sanctioned_amount_inr: { label: "Sanctioned amount", unit: "currency", description: "Visible sanctioned amount for the work.", interpretation: "Compare the work's sanction with lifecycle-similar works." },
  schedule_elapsed_ratio_as_of: { label: "Share of planned schedule elapsed", unit: "ratio", description: "Elapsed schedule time relative to planned duration.", interpretation: "Values above one indicate elapsed time exceeds the recorded planned duration." },
  technical_estimate_amount_inr: { label: "Technical estimate", unit: "currency", description: "Recorded technical estimate amount.", interpretation: "Compare the estimate with recommendation, sanction, and similar works." },
};

const ADDITIONAL_METRICS: Record<string, MetricMetadata> = {
  days_recommendation_to_sanction: { label: "Recommendation-to-sanction time", unit: "days", description: "Recorded days between recommendation and sanction.", interpretation: "Used as model context, not a causal finding." },
  days_sanction_to_expected_start: { label: "Sanction-to-expected-start time", unit: "days", description: "Recorded days from sanction to expected start.", interpretation: "Used as model context, not a causal finding." },
  largest_payment_inr_as_of: { label: "Largest released payment", unit: "currency", description: "Largest released payment visible at the snapshot.", interpretation: "A payment amount used as model context." },
  mean_payment_inr_as_of: { label: "Average released payment", unit: "currency", description: "Mean released-payment amount at the snapshot.", interpretation: "A payment amount used as model context." },
  planned_duration_days: { label: "Planned work duration", unit: "days", description: "Recorded planned duration.", interpretation: "Used as model context, not a causal finding." },
  progress_report_count: { label: "Progress reports recorded", unit: "count", description: "Operational count of progress reports.", interpretation: "Aggregate operational context only." },
  released_payment_amount_inr: { label: "Released payment amount", unit: "currency", description: "Released amount in the trend period.", interpretation: "Aggregate operational context only." },
  released_payment_count: { label: "Released payment count", unit: "count", description: "Number of released payments in the trend period.", interpretation: "Aggregate operational context only." },
};

function metadata(metric: string): MetricMetadata | undefined {
  return PEER_METRICS[metric] ?? ADDITIONAL_METRICS[metric];
}

export const FAMILY_LABELS: Record<string, string> = {
  ANOMALY: "Unusual Pattern Detection",
  PEER_DEVIATION: "Peer Comparison",
  DUPLICATE_REVIEW: "Duplicate Work Review",
  PAYMENT_EXECUTION: "Payments & Fund-Progress",
  OBSERVED_CONDITIONS: "Observed Cost / Delay Conditions",
  COMPLIANCE: "MPLADS Compliance Monitoring",
  COST_PREDICTION: "Cost-Overrun Early Warning",
  OPERATIONAL_TREND_CONTEXT: "Operational Trend Context",
};

export const FAMILY_EXPLANATIONS: Record<string, string> = {
  ANOMALY: "The work is statistically unusual within its lifecycle comparison set.",
  PEER_DEVIATION: "One or more values differ materially from lifecycle-similar works.",
  DUPLICATE_REVIEW: "A corroborated work pair warrants a side-by-side file review.",
  PAYMENT_EXECUTION: "Recorded payment or fund-progress evidence requires reconciliation.",
  OBSERVED_CONDITIONS: "The current snapshot contains an already-observed schedule or sanction condition.",
  COMPLIANCE: "A deterministic MPLADS rule result requires officer attention.",
  COST_PREDICTION: "A limited-reliability model provides secondary early-warning context.",
  OPERATIONAL_TREND_CONTEXT: "The surrounding operational group differs from its historical baseline.",
};

export const ATTENTION_LABELS: Record<string, string> = {
  NORMAL: "Normal", LOW_ATTENTION: "Low Attention", MEDIUM_ATTENTION: "Medium Attention",
  HIGH_ATTENTION: "High Attention", IMMEDIATE_PRIORITY: "Immediate Priority",
};

export const DOCUMENT_STATE_LABELS: Record<string, string> = {
  RECORDED: "Recorded", NOT_YET_APPLICABLE: "Not yet applicable",
  EXPECTED_AFTER_COMPLETION: "Expected after completion",
  NOT_RECORDED_AS_OF_SNAPSHOT: "Not recorded as of snapshot", REQUIRES_REVIEW: "Requires Review",
  NON_COMPLIANT: "Non-Compliant", INSUFFICIENT_DATA: "Insufficient data",
  FUTURE_DATED: "Future-dated / not yet visible as of snapshot",
};

export const FOLLOW_UP_ACTION_LABELS: Record<string, string> = {
  REQUEST_CLARIFICATION: "Request Clarification",
  REQUEST_SUPPORTING_DOCUMENTS: "Request Supporting Documents",
  FINANCIAL_RECONCILIATION_REQUIRED: "Financial Reconciliation Required",
  REQUEST_UPDATED_PROGRESS_REPORT: "Request Updated Progress Report",
  SCHEDULE_FIELD_VERIFICATION: "Schedule / Field Verification",
  DUPLICATE_WORK_COMPARISON_REQUIRED: "Duplicate Work Comparison Required",
  REVIEW_REVISED_SANCTION: "Review Revised Sanction",
  ESCALATE_FOR_DETAILED_REVIEW: "Escalate for Detailed Review",
  NO_FURTHER_ACTION: "No Further Action",
  CLOSE_AFTER_VERIFICATION: "Close After Verification",
};

export type ReadinessGroup = "Recorded" | "Requires Review" | "Not Recorded" | "Not Applicable";

export function readinessGroup(value: unknown): ReadinessGroup {
  const status = String(value ?? "");
  if (status === "RECORDED") return "Recorded";
  if (["REQUIRES_REVIEW", "NON_COMPLIANT"].includes(status)) return "Requires Review";
  if (["EXPECTED_AFTER_COMPLETION", "NOT_APPLICABLE", "NOT_YET_APPLICABLE"].includes(status)) return "Not Applicable";
  return "Not Recorded";
}

export const MODEL_STATUS_LABELS: Record<string, string> = {
  PROTOTYPE_WEAK_DISCRIMINATION: "Model reliability: Limited", NOT_APPLICABLE: "Not applicable", UNAVAILABLE: "Unavailable",
};

export const SEVERITY_LABELS: Record<string, string> = {
  NORMAL: "Normal", LOW_ATTENTION: "Low Attention", REQUIRES_REVIEW: "Requires Review",
  HIGH_ATTENTION: "High Attention", VERY_HIGH_ATTENTION: "Very High Attention",
  REVIEW: "Requires Review", STRONG_WARNING: "High-Attention Review",
};

export const EVIDENCE_LABELS: Record<string, string> = {
  LIFECYCLE_ANOMALY_PERCENTILE: "Within-lifecycle unusualness",
  LIFECYCLE_ANOMALY_TOP_DECILE: "High within-lifecycle unusualness",
  STATISTICAL_PEER_OUTLIER: "Unusual peer comparison",
  DUPLICATE_REVIEW_CANDIDATE: "Possible duplicate work",
  DAY4_1_CORROBORATED_REVIEW_CANDIDATE: "Corroborated duplicate-review candidate",
  PERSISTENT_FUND_PROGRESS_REVIEW: "Persistent financial-vs-physical progress mismatch",
  CURRENT_LARGE_POSITIVE_FUND_GAP: "Current financial-vs-physical progress mismatch",
  PAYMENT_AUTH_BEFORE_REQUEST: "Payment authorization recorded before request",
  RELEASED_TOTAL_EXCEEDS_SANCTION: "Released payments exceed the visible sanction",
  OBSERVED_OVERDUE: "Observed overdue work",
  OBSERVED_OVERDUE_AS_OF: "Observed overdue work",
  OBSERVED_OVER_SANCTION: "Observed amount above sanction",
  OBSERVED_OVER_SANCTION_AS_OF: "Observed amount above sanction",
  RAW_XGBOOST_SECONDARY_TOP_DECILE: "Cost-overrun early warning",
  OPERATIONAL_TREND_DEVIATION: "Operational trend context",
  SUPPORTED_LATEST_MONTH_OPERATIONAL_TREND: "Operational trend context",
  ZERO_VALUE_RELEASED_PAYMENT: "Zero-value released payment record",
};

export function hasValue(value: unknown): boolean {
  return value !== null && value !== undefined && value !== "" && String(value).toLowerCase() !== "nan";
}

export function formatMetric(metric: string, value: unknown): string {
  if (!hasValue(value) || typeof value !== "number") return "Not available";
  const meta = metadata(metric);
  if (!meta) return number.format(value);
  if (meta.unit === "currency") return inr.format(value);
  if (meta.unit === "percent") return `${number.format(value)}%`;
  if (meta.unit === "percentage_points") return `${number.format(value)} percentage points`;
  if (meta.unit === "days") return `${number.format(value)} days`;
  if (meta.unit === "count") return number.format(value);
  if (meta.unit === "percent_per_30_days") return `${number.format(value)}% per 30 days`;
  if (metric === "largest_payment_share_as_of") return `${number.format(value * 100)}%`;
  return number.format(value);
}

export function formatFact(value: unknown, kind: unknown): string {
  if (!hasValue(value)) return "Not available";
  const numeric = typeof value === "number" ? value : Number(value);
  if (kind === "currency" && Number.isFinite(numeric)) return inr.format(numeric);
  if (kind === "percent" && Number.isFinite(numeric)) return `${number.format(numeric)}%`;
  if (kind === "percentage_points" && Number.isFinite(numeric)) return `${number.format(numeric)} percentage points`;
  if (kind === "score" && Number.isFinite(numeric)) return number.format(numeric);
  if (kind === "days" && Number.isFinite(numeric)) return `${number.format(Math.round(numeric))} days`;
  if (kind === "date") {
    const date = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
    return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(date);
  }
  return String(value);
}

export function formatCompactInr(value: unknown): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "Not available";
  const compact = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
  const absolute = Math.abs(numeric);
  if (absolute >= 10_000_000) return `₹${compact.format(numeric / 10_000_000)} crore`;
  if (absolute >= 100_000) return `₹${compact.format(numeric / 100_000)} lakh`;
  return inr.format(numeric);
}

export function attentionLabel(value: unknown): string {
  return ATTENTION_LABELS[String(value ?? "")] ?? friendlyEvidence(value);
}

export function documentStateLabel(value: unknown): string {
  return DOCUMENT_STATE_LABELS[String(value ?? "")] ?? friendlyEvidence(value);
}

export function peerObservedValue(row: Row): unknown {
  if (hasValue(row.observed_value)) return row.observed_value;
  if (hasValue(row.project_value)) return row.project_value;
  return null;
}

export function metricLabel(metric: unknown): string {
  const key = String(metric ?? "");
  return metadata(key)?.label ?? friendlyEvidence(key || "Metric");
}

export function friendlyEvidence(value: unknown): string {
  const key = String(value ?? "");
  return EVIDENCE_LABELS[key] ?? key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function familyLabel(value: unknown): string {
  const key = String(value ?? "");
  return FAMILY_LABELS[key] ?? friendlyEvidence(key);
}

export function familyExplanation(value: unknown): string {
  return FAMILY_EXPLANATIONS[String(value ?? "")] ?? "A governed evidence family contributes to review urgency.";
}

export function humanizeNarrative(value: unknown): string {
  let rendered = String(value ?? "");
  const replacements: Record<string, string> = {
    ...Object.fromEntries(Object.entries(PEER_METRICS).map(([key, meta]) => [key, meta.label])),
    ...Object.fromEntries(Object.entries(ADDITIONAL_METRICS).map(([key, meta]) => [key, meta.label])),
    ...FAMILY_LABELS,
    ...EVIDENCE_LABELS,
  };
  Object.entries(replacements).sort(([a], [b]) => b.length - a.length).forEach(([key, label]) => {
    rendered = rendered.replaceAll(key, label);
  });
  rendered = rendered
    .replaceAll("overrun_pct=", "amount above sanction: ")
    .replaceAll("days=", "days: ")
    .replaceAll("score=", "score: ")
    .replaceAll("Observed overdue=", "Observed overdue: ")
    .replaceAll("observed over sanction=", "observed over sanction: ");
  return rendered.replace(/-?\d+\.\d{2,}/g, (match) => number.format(Number(match)));
}

export function complianceState(result: unknown): DisplayState {
  const value = String(result ?? "");
  if (value === "NON_COMPLIANT") return "strong_issue";
  if (value === "REVIEW") return "review";
  if (value === "PASS") return "pass";
  if (value === "NOT_APPLICABLE") return "not_applicable";
  return "insufficient";
}

export function contributionSum(rows: Row[]): number {
  return rows.reduce((sum, row) => sum + Number(row.contribution_points ?? 0), 0);
}

export function asRows(value: unknown): Row[] {
  return Array.isArray(value) ? value as Row[] : [];
}

export function asRecord(value: unknown): Row {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Row : {};
}
