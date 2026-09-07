export type Role = "MOSPI" | "STATE" | "DISTRICT" | "IA" | "MP";
export type Scope = { role: Role; state?: string; district?: string; mp_id?: string; agency_id?: string };
export interface ScopeOptions { roles: Role[]; states: string[];
  districts: { state_name: string; district: string }[];
  mps: { mp_id: string; mp_name: string; state_name?: string | null; constituency?: string | null; districts?: string[] }[];
  agencies: { agency_id: string; agency_name: string; state_name?: string | null; district?: string | null }[];
  sectors?: string[]; sub_sectors?: string[];
  dataset_profile?: string; synthetic_demo_data?: boolean }
export interface Overview { dataset_profile: string; synthetic_demo_data: boolean; synthetic_disclaimer: string;
  role: Role; section_order: string[]; primary_question: string;
  overview: Record<string, number | string | null>; morning_brief: { generation_mode: string; facts: string[]; ai_explicit_action_only: boolean };
  project_status: Record<string, number>; fund_flow: Record<string, number | string | null>;
  sector_distribution: Record<string, unknown>[]; comparison: { level: string; items: Record<string, unknown>[] };
  map: { rendering: string; license_note: string; layer_options: string[]; items: Record<string, unknown>[] };
  projects_requiring_attention: Record<string, unknown>[]; recommended_actions: string[]; decision_workflow: string[];
  language_note: string }
export interface QueueItem { work_id: string; mp_id: string; state_name: string; district: string; sector: string;
  sub_sector: string; lifecycle_stage: string; current_status: string;
  sanctioned_amount_inr: number | null; review_priority_score_0_100: number;
  review_priority_band: string; requires_review: boolean; attention_level: string;
  observed_delay: boolean; observed_cost_overrun: boolean; has_duplicate_candidate: boolean; monthly_evidence_status: string }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number; total_pages: number }
export interface WorkDetail { dataset_profile: string; synthetic_demo_data: boolean; synthetic_disclaimer: string;
  header: Record<string, unknown>; project_details: Record<string, unknown>;
  monitoring_health: Record<string, unknown>[]; anomalies_irregularities: Record<string, unknown>[];
  key_risk_areas: Record<string, Record<string, unknown>>; progress_schedule: Record<string, unknown>;
  geo_evidence: Record<string, unknown>; records_completion: Record<string, unknown>;
  ai_explanation: Record<string, unknown>; officer_review: Record<string, unknown>; technical_details: Record<string, unknown> }

export interface Recommendation {
  recommendation_id: string; status: string; status_label: string; mp_id: string; mp_name: string;
  title: string; sector: string; sub_sector: string; description: string; public_benefit: string;
  state: string; district: string; block: string; village: string; pincode?: string | null;
  latitude?: number | null; longitude?: number | null; proposed_project_cost_inr: number;
  expected_duration_months?: number | null; preferred_start_period?: string | null;
  sanctioned_cost_inr?: number | null; sanction_date?: string | null; implementing_agency?: string | null;
  expected_start_date?: string | null; expected_completion_date?: string | null;
  precheck?: Record<string, unknown> | null; documents: Record<string, unknown>[];
  payments: Record<string, unknown>[]; progress_updates: Record<string, unknown>[];
  runtime_checks: Record<string, unknown>[]; activity: Record<string, unknown>[];
  tracker: { key: string; label: string; state: "COMPLETE" | "CURRENT" | "UPCOMING" }[];
  created_at: string; updated_at: string;
}

export interface MyWorkItem {
  record_type: "ANALYTICAL_WORK" | "RUNTIME_RECOMMENDATION"; id: string; title: string;
  location: string; cost_inr: number | null; status: string; category: "RECOMMENDED" | "ONGOING" | "COMPLETED";
  progress_pct?: number | null; needs_attention: boolean; updated_at?: string | null;
}
