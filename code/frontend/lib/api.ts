import { z } from "zod";
import type { Overview, Page, QueueItem, Scope, ScopeOptions, WorkDetail } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const looseRecord = z.record(z.string(), z.unknown());
const overviewSchema = z.object({ work_count: z.number(), review_queue_count: z.number(),
  mean_review_priority: z.number().nullable(), priority_bands: z.record(z.string(), z.number()),
  lifecycle_counts: z.record(z.string(), z.number()), attention_levels: z.record(z.string(), z.number()),
  attention_level_percentages: z.record(z.string(), z.number()), attention_level_labels: z.record(z.string(), z.string()),
  requires_review_count: z.number(), immediate_priority_count: z.number(), attention_level_note: z.string(),
  natural_distribution_note: z.string(), financial_snapshot: looseRecord,
  review_signals: looseRecord, as_of_date: z.string().nullable(), language_note: z.string() });
const scopeOptionsSchema = z.object({ roles: z.array(z.enum(["MOSPI", "STATE", "DISTRICT", "MP"])),
  states: z.array(z.string()), districts: z.array(z.object({ state_name: z.string(), district: z.string() })),
  mps: z.array(z.object({ mp_id: z.string(), mp_name: z.string(), state_name: z.string().nullish(), constituency: z.string().nullish() })) });
const pageSchema = z.object({ items: z.array(looseRecord), page: z.number(), page_size: z.number(), total: z.number(), total_pages: z.number() });
const alertsSchema = z.object({
  items: z.array(looseRecord),
  summary: z.array(z.object({
    alert_type: z.string(), category: z.string(), label: z.string(), work_count: z.number(),
    alert_count: z.number(), status: z.string(), actionable: z.boolean(), short_explanation: z.string(),
  })),
  total: z.number(), returned: z.number(), limit: z.number(),
});
const workSchema = z.object({ profile: looseRecord, priority: looseRecord, contributions: z.array(looseRecord),
  contribution_sum: z.number(), alerts: z.array(looseRecord), anomaly: looseRecord,
  peer_benchmark: looseRecord, duplicates: looseRecord, payments: looseRecord,
  compliance: looseRecord, prediction: looseRecord, trend_context: looseRecord,
  explanation: looseRecord, reviews: z.array(looseRecord), current_review_status: z.string(),
  presentation: looseRecord });

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function scopeParams(scope: Scope) {
  const params = new URLSearchParams({ role: scope.role });
  if (scope.state) params.set("state", scope.state);
  if (scope.district) params.set("district", scope.district);
  if (scope.mp_id) params.set("mp_id", scope.mp_id);
  return params;
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } }); }
  catch { throw new ApiError("Backend is unavailable. Start the FastAPI service and try again.", 0); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`, response.status);
  }
  return schema.parse(await response.json());
}

export const api = {
  scopeOptions: () => request<ScopeOptions>("/api/v1/scope/options", scopeOptionsSchema),
  overview: (scope: Scope) => request<Overview>(`/api/v1/dashboard/overview?${scopeParams(scope)}`, overviewSchema as unknown as z.ZodType<Overview>),
  queue: (scope: Scope, filters: Record<string, string | number | boolean | undefined>) => {
    const params = scopeParams(scope);
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
    return request<Page<QueueItem>>(`/api/v1/review-queue?${params}`, pageSchema as unknown as z.ZodType<Page<QueueItem>>);
  },
  work: (workId: string) => request<WorkDetail>(`/api/v1/works/${encodeURIComponent(workId)}`, workSchema as z.ZodType<WorkDetail>),
  caseReportUrl: (workId: string) => `${API_BASE}/api/v1/works/${encodeURIComponent(workId)}/case-report.pdf`,
  trends: (scope: Scope, filters: Record<string, string | number | undefined>) => {
    const params = scopeParams(scope); Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== "") params.set(k, String(v)); });
    return request<{ items: Record<string, unknown>[]; total: number; returned: number }>(`/api/v1/trends?${params}`, z.object({ items: z.array(looseRecord), total: z.number(), returned: z.number(), limit: z.number() }));
  },
  hotspots: (scope: Scope) => request<{ items: Record<string, unknown>[]; total: number }>(`/api/v1/hotspots?${scopeParams(scope)}`, z.object({ items: z.array(looseRecord), total: z.number(), returned: z.number(), limit: z.number() })),
  alerts: (scope: Scope) => request(`/api/v1/alerts?${scopeParams(scope)}&limit=1`, alertsSchema),
  explain: (workId: string, useLlm: boolean) => request<Record<string, unknown>>(`/api/v1/works/${encodeURIComponent(workId)}/explain`, looseRecord, { method: "POST", body: JSON.stringify({ use_llm: useLlm }) }),
  addReview: (workId: string, payload: Record<string, string>) => request<Record<string, unknown>>(`/api/v1/works/${encodeURIComponent(workId)}/reviews`, looseRecord, { method: "POST", body: JSON.stringify(payload) }),
};
