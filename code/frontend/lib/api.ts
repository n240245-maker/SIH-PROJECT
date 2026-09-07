import { z } from "zod";
import type { MyWorkItem, Overview, Page, QueueItem, Recommendation, Scope, ScopeOptions, WorkDetail } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DATASET_PROFILE = process.env.NEXT_PUBLIC_MPLADS_DATASET_PROFILE ?? "demo_v2";
const API_PREFIX = DATASET_PROFILE === "baseline" ? "/api/v1" : "/api/v2";
const looseRecord = z.record(z.string(), z.unknown());

const scopeOptionsSchema = z.object({
  roles: z.array(z.enum(["MOSPI", "STATE", "DISTRICT", "IA", "MP"])),
  states: z.array(z.string()),
  districts: z.array(z.object({ state_name: z.string(), district: z.string() })),
  mps: z.array(z.object({ mp_id: z.string(), mp_name: z.string(), state_name: z.string().nullish(), constituency: z.string().nullish(), districts: z.array(z.string()).optional() })),
  agencies: z.array(z.object({ agency_id: z.string(), agency_name: z.string(), state_name: z.string().nullish(), district: z.string().nullish() })).default([]),
  sectors: z.array(z.string()).optional(), sub_sectors: z.array(z.string()).optional(),
  dataset_profile: z.string().optional(), synthetic_demo_data: z.boolean().optional(),
});

const overviewSchema = z.object({
  dataset_profile: z.string(), synthetic_demo_data: z.boolean(), synthetic_disclaimer: z.string(),
  role: z.enum(["MOSPI", "STATE", "DISTRICT", "IA", "MP"]), section_order: z.array(z.string()), primary_question: z.string(),
  overview: looseRecord, morning_brief: z.object({ generation_mode: z.string(), facts: z.array(z.string()), ai_explicit_action_only: z.boolean() }),
  project_status: z.record(z.string(), z.number()), fund_flow: looseRecord,
  sector_distribution: z.array(looseRecord), comparison: z.object({ level: z.string(), items: z.array(looseRecord) }),
  map: z.object({ rendering: z.string(), license_note: z.string(), layer_options: z.array(z.string()), items: z.array(looseRecord) }),
  projects_requiring_attention: z.array(looseRecord), recommended_actions: z.array(z.string()), decision_workflow: z.array(z.string()),
  language_note: z.string(),
});

const pageSchema = z.object({ items: z.array(looseRecord), page: z.number(), page_size: z.number(), total: z.number(), total_pages: z.number() });
const alertsSchema = z.object({ items: z.array(looseRecord), summary: z.array(looseRecord).default([]), total: z.number(), returned: z.number(), limit: z.number() });
const workSchema = z.object({
  dataset_profile: z.string(), synthetic_demo_data: z.boolean(), synthetic_disclaimer: z.string(),
  header: looseRecord, project_details: looseRecord, monitoring_health: z.array(looseRecord),
  anomalies_irregularities: z.array(looseRecord), key_risk_areas: z.record(z.string(), looseRecord),
  progress_schedule: looseRecord, geo_evidence: looseRecord, records_completion: looseRecord,
  ai_explanation: looseRecord, officer_review: looseRecord, technical_details: looseRecord,
});
const recommendationSchema = looseRecord as unknown as z.ZodType<Recommendation>;
const recommendationPageSchema = z.object({
  items: z.array(recommendationSchema), page: z.number(), page_size: z.number(),
  total: z.number(), total_pages: z.number(),
}) as z.ZodType<Page<Recommendation>>;
const myWorksPageSchema = z.object({
  items: z.array(looseRecord), page: z.number(), page_size: z.number(),
  total: z.number(), total_pages: z.number(),
}) as unknown as z.ZodType<Page<MyWorkItem>>;

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function scopeParams(scope: Scope) {
  const params = new URLSearchParams({ role: scope.role });
  if (scope.state) params.set("state", scope.state);
  if (scope.district) params.set("district", scope.district);
  if (scope.mp_id) params.set("mp_id", scope.mp_id);
  if (scope.agency_id) params.set("agency_id", scope.agency_id);
  return params;
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError("The local FastAPI service is unavailable. Start it and try again.", 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail) && detail[0] && typeof detail[0].msg === "string"
        ? detail[0].msg.replace(/^Value error, /, "")
        : `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return schema.parse(await response.json());
}

export const api = {
  datasetProfile: DATASET_PROFILE,
  scopeOptions: () => request<ScopeOptions>(`${API_PREFIX}/scope/options`, scopeOptionsSchema as z.ZodType<ScopeOptions>),
  overview: (scope: Scope) => request<Overview>(`${API_PREFIX}/dashboard/overview?${scopeParams(scope)}`, overviewSchema as z.ZodType<Overview>),
  queue: (scope: Scope, filters: Record<string, string | number | boolean | undefined>) => {
    const params = scopeParams(scope);
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
    return request<Page<QueueItem>>(`${API_PREFIX}/review-queue?${params}`, pageSchema as unknown as z.ZodType<Page<QueueItem>>);
  },
  work: (workId: string, scope: Scope) => request<WorkDetail>(`${API_PREFIX}/works/${encodeURIComponent(workId)}?${scopeParams(scope)}`, workSchema as z.ZodType<WorkDetail>),
  caseReportUrl: (workId: string, scope: Scope) => `${API_BASE}${API_PREFIX}/works/${encodeURIComponent(workId)}/case-report.pdf?${scopeParams(scope)}`,
  alerts: (scope: Scope) => request(`${API_PREFIX}/alerts?${scopeParams(scope)}&limit=200`, alertsSchema),
  explain: (workId: string, scope: Scope, useLlm = true) => request<Record<string, unknown>>(`${API_PREFIX}/works/${encodeURIComponent(workId)}/explain?${scopeParams(scope)}`, looseRecord, { method: "POST", body: JSON.stringify({ use_llm: useLlm }) }),
  dashboardBrief: (scope: Scope) => request<Record<string, unknown>>(`${API_PREFIX}/dashboard/brief?${scopeParams(scope)}`, looseRecord, { method: "POST", body: JSON.stringify({ use_llm: false }) }),
  addReview: (workId: string, scope: Scope, payload: Record<string, string>) => request<Record<string, unknown>>(`${API_PREFIX}/works/${encodeURIComponent(workId)}/reviews?${scopeParams(scope)}`, looseRecord, { method: "POST", body: JSON.stringify(payload) }),
  createGeoEvidence: (workId: string, scope: Scope, payload: Record<string, unknown>) => request<Record<string, unknown>>(`${API_PREFIX}/works/${encodeURIComponent(workId)}/geo-evidence?${scopeParams(scope)}`, looseRecord, { method: "POST", body: JSON.stringify(payload) }),
  verifyGeoEvidence: (evidenceId: string, scope: Scope, payload: Record<string, unknown>) => request<Record<string, unknown>>(`${API_PREFIX}/geo-evidence/${encodeURIComponent(evidenceId)}/verify?${scopeParams(scope)}`, looseRecord, { method: "POST", body: JSON.stringify(payload) }),
  imageUrl: (path: unknown, scope: Scope) => `${API_BASE}${String(path ?? "")}?${scopeParams(scope)}`,
  recommendations: (scope: Scope, filters: { page?: number; page_size?: number; search?: string; status?: string } = {}) => {
    const params = scopeParams(scope);
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
    return request<Page<Recommendation>>(`/api/v1/recommendations?${params}`, recommendationPageSchema);
  },
  recommendation: (recommendationId: string, scope: Scope) => request<Recommendation>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}?${scopeParams(scope)}`, recommendationSchema),
  createRecommendation: (scope: Scope, payload: Record<string, unknown>) => request<Recommendation>(`/api/v1/recommendations?${scopeParams(scope)}`, recommendationSchema, { method: "POST", body: JSON.stringify(payload) }),
  precheckRecommendation: (recommendationId: string, scope: Scope) => request<Record<string, unknown>>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/precheck?${scopeParams(scope)}`, looseRecord, { method: "POST", body: "{}" }),
  recommendationAction: (recommendationId: string, scope: Scope, payload: Record<string, unknown>) => request<Recommendation>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/actions?${scopeParams(scope)}`, recommendationSchema, { method: "POST", body: JSON.stringify(payload) }),
  uploadRecommendationDocument: (recommendationId: string, scope: Scope, actorLabel: string, payload: Record<string, unknown>) => {
    const params = scopeParams(scope); params.set("actor_label", actorLabel);
    return request<Record<string, unknown>>(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/documents?${params}`, looseRecord, { method: "POST", body: JSON.stringify(payload) });
  },
  myWorks: (scope: Scope, filters: { page?: number; page_size?: number; category?: string; search?: string } = {}) => {
    const params = scopeParams(scope);
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
    return request<Page<MyWorkItem>>(`/api/v1/recommendations/my-works?${params}`, myWorksPageSchema);
  },
};
