export type Role = "MOSPI" | "STATE" | "DISTRICT" | "MP";
export type Scope = { role: Role; state?: string; district?: string; mp_id?: string };
export interface ScopeOptions { roles: Role[]; states: string[];
  districts: { state_name: string; district: string }[];
  mps: { mp_id: string; mp_name: string; state_name?: string | null; constituency?: string | null }[] }
export interface Overview { work_count: number; review_queue_count: number; mean_review_priority: number | null;
  priority_bands: Record<string, number>; lifecycle_counts: Record<string, number>;
  attention_levels: Record<string, number>; attention_level_percentages: Record<string, number>;
  attention_level_labels: Record<string, string>; requires_review_count: number; immediate_priority_count: number;
  attention_level_note: string; natural_distribution_note: string;
  financial_snapshot: { sanctioned_amount_inr: number; released_amount_inr: number;
    observed_over_sanction_count: number; observed_overdue_count: number };
  review_signals: { duplicate_review_work_count: number; payment_evidence_work_count: number;
    compliance_review_work_count: number }; as_of_date: string | null; language_note: string }
export interface QueueItem { work_id: string; mp_id: string; state_name: string; district: string; sector: string;
  sub_sector: string; lifecycle_stage: string; source_current_status: string;
  sanctioned_amount_inr: number | null; review_priority_score_0_100: number;
  review_priority_band: string; review_priority_rank_overall: number;
  fusion_evidence_coverage_pct: number; top_contributor_1_family: string;
  top_contributor_1_summary: string; current_review_status: string; alerts: Record<string, unknown>[];
  attention_level: string; attention_level_label: string; requires_review: boolean; attention_reasons: string[] }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number; total_pages: number }
export interface WorkDetail { profile: Record<string, unknown>; priority: Record<string, unknown>;
  contributions: Record<string, unknown>[]; contribution_sum: number; alerts: Record<string, unknown>[];
  anomaly: Record<string, unknown>; peer_benchmark: Record<string, unknown>;
  duplicates: Record<string, unknown>; payments: Record<string, unknown>;
  compliance: Record<string, unknown>; prediction: Record<string, unknown>;
  trend_context: Record<string, unknown>; explanation: Record<string, unknown>;
  reviews: Record<string, unknown>[]; current_review_status: string;
  presentation: Record<string, unknown> }
