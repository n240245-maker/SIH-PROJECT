"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, ChevronRight, Download, FileCheck2, Info, MapPin, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, ReactNode, useState } from "react";

import { GeoEvidenceActions } from "@/components/geo-evidence-actions";
import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number, text } from "@/lib/format";
import { FOLLOW_UP_ACTION_LABELS, asRecord, asRows, friendlyEvidence } from "@/lib/presentation";
import { useScope } from "@/lib/scope";

type Row = Record<string, unknown>;
const SECTION_LINKS = [
  ["project-details", "1. Project Details"], ["monitoring-health", "2. Monitoring Health"],
  ["anomalies-irregularities", "3. Anomalies & Irregularities"], ["key-risk-areas", "4. Key Risk Areas"],
  ["progress-schedule", "5. Progress & Schedule"], ["geo-evidence", "6. Geo-Tagged Progress Evidence"],
  ["records-completion", "7. Records & Completion Readiness"], ["ai-explanation", "8. AI-Assisted Case Explanation"],
  ["officer-review", "9. Officer Review & Corrective Action"],
] as const;

function bool(value: unknown) { return value === true || String(value).toLowerCase() === "true"; }
function money(value: unknown) { const numeric = Number(value); return Number.isFinite(numeric) ? inr.format(numeric) : "Not available"; }
function numeric(value: unknown, suffix = "") { const parsed = Number(value); return Number.isFinite(parsed) ? `${number.format(parsed)}${suffix}` : "Not available"; }
function statusClass(value: unknown) { const status = String(value ?? "").toLowerCase(); return status.includes("normal") || status.includes("good") || status.includes("recorded") || status.includes("schedule") ? "ok" : status.includes("review") || status.includes("delay") || status.includes("overrun") || status.includes("comparison") || status.includes("overdue") ? "review" : "neutral"; }

function StatusPill({ value }: { value: unknown }) { return <span className={`dossier-status status-${statusClass(value)}`}>{text(value).replaceAll("_", " ")}</span>; }
function Technical({ children }: { children: ReactNode }) { return <details className="technical-details"><summary>Technical details</summary><div>{children}</div></details>; }
function Fact({ label, value, kind, warning = false }: { label: string; value: unknown; kind?: "money" | "percent"; warning?: boolean }) {
  const rendered = kind === "money" ? money(value) : kind === "percent" ? numeric(value, "%") : text(value);
  return <div className={`dossier-fact ${warning ? "dossier-fact-warning" : ""}`}><dt>{label}</dt><dd>{rendered}</dd></div>;
}

function RiskCard({ title, status, children }: { title: string; status: unknown; children: ReactNode }) {
  return <details className={`risk-card risk-${statusClass(status)}`}><summary><span><strong>{title}</strong><StatusPill value={status} /></span><ChevronRight size={18} aria-hidden="true" /></summary><div className="risk-card-body">{children}</div></details>;
}

function ReviewDisclaimer() {
  return <div className="review-note"><ShieldCheck size={18} /><div><strong>Authorized human review remains final</strong><p>This prototype prioritizes evidence for verification. It does not establish fraud, wrongdoing, liability, or an official MPLADS decision.</p></div></div>;
}

function Explanation({ value }: { value: Row }) {
  const why = asRows(value.why_flagged); const issues = Array.isArray(value.main_issues) ? value.main_issues : [];
  return <div className="explanation-body"><p className="explanation-summary">{text(value.summary ?? value.what_the_work_is, "A deterministic explanation is available from the structured case evidence.")}</p>
    {Array.isArray(value.what_happened) && <div><h3>What happened</h3><ul>{value.what_happened.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul></div>}
    {!!issues.length && <div><h3>Main issues</h3><ul>{issues.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul></div>}
    {!!why.length && <div><h3>Why this work was flagged</h3>{why.map((row, index) => <article className="explanation-evidence" key={`${row.family}-${index}`}><strong>{friendlyEvidence(row.family)}</strong><p>{text(row.finding)}</p><small>{text(row.interpretation)}</small></article>)}</div>}
    {Array.isArray(value.verification_steps) && <div><h3>Recommended verification</h3><ol>{value.verification_steps.map((item) => <li key={String(item)}>{String(item)}</li>)}</ol></div>}
    {value.decision_statement != null && <p className="decision-statement">{text(value.decision_statement)}</p>}
  </div>;
}

export default function WorkDetailPage() {
  const workId = String(useParams<{ workId: string }>().workId);
  const { scope } = useScope(); const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["v2-work", workId, scope], queryFn: () => api.work(workId, scope) });
  const explain = useMutation({ mutationFn: () => api.explain(workId, scope, true) });
  const [actor, setActor] = useState(""); const [status, setStatus] = useState("IN_REVIEW");
  const [action, setAction] = useState("REQUEST_CLARIFICATION"); const [note, setNote] = useState("");
  const review = useMutation({ mutationFn: () => api.addReview(workId, scope, { actor_role: scope.role, actor_label: actor, status, follow_up_action: action, scope_label: [scope.state, scope.district, scope.mp_id, scope.agency_id].filter(Boolean).join(" / ") || "National", note }), onSuccess: async () => { setNote(""); await queryClient.invalidateQueries({ queryKey: ["v2-work", workId] }); } });
  const submitReview = (event: FormEvent) => { event.preventDefault(); review.mutate(); };
  if (query.isLoading) return <LoadingState label="Loading the authority-scoped work dossier…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;

  const d = query.data; const header = d.header; const project = d.project_details;
  const risks = d.key_risk_areas; const funds = asRecord(risks.fund_utilization); const delays = asRecord(risks.delays);
  const cost = asRecord(risks.cost_overrun); const costTechnical = asRecord(cost.technical); const duplicate = asRecord(risks.duplicate_works);
  const timeline = asRows(d.progress_schedule.timeline); const latestProgress = asRecord(d.progress_schedule.latest_progress);
  const geo = d.geo_evidence; const geoSummary = asRecord(geo.summary); const geoItems = asRows(geo.items);
  const records = d.records_completion; const recordStatuses = asRecord(records.statuses); const recordRows = asRows(records.records);
  const officer = d.officer_review; const reviews = asRows(officer.reviews);
  const baseExplanation = asRecord(d.ai_explanation.explanation); const generated = explain.data ? asRecord(explain.data.explanation) : null;
  const explanationMode = generated ? text(explain.data?.generation_mode) : text(baseExplanation.generation_mode, "DETERMINISTIC_FALLBACK");

  return <>
    <header className="dossier-header"><div><p className="eyebrow">{text(header.workspace)} · synthetic demo-v2</p><h1>{text(header.project_title)}</h1><p><strong>{workId}</strong> · {text(header.location)}</p></div><div className="dossier-priority"><span>Review Priority</span><strong>{numeric(header.review_priority_score_0_100)}</strong><StatusPill value={header.attention_level} /></div></header>
    <div className="synthetic-banner"><Info size={16} /><span>{d.synthetic_disclaimer}</span></div>
    <nav className="section-nav dossier-nav" aria-label="Work dossier sections">{SECTION_LINKS.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav>

    <Section id="project-details" title="1. Project Details" subtitle="Recorded project facts only; analytical signals appear in later sections."><dl className="dossier-facts"><Fact label="Work ID" value={project.work_id} /><Fact label="Lifecycle" value={project.lifecycle} /><Fact label="Recorded work status" value={project.recorded_work_status} /><Fact label="Officer case status" value={project.officer_case_status} /><Fact label="Member of Parliament" value={project.member_of_parliament} /><Fact label="Constituency" value={project.constituency} /><Fact label="Location" value={project.location} /><Fact label="Sanctioned amount" value={project.sanctioned_amount_inr} kind="money" /><Fact label="Released payments" value={project.released_payments_inr} kind="money" warning={bool(asRecord(project.field_highlights).released_payments_inr)} /><Fact label="Physical progress" value={project.physical_progress_pct} kind="percent" /><Fact label="Financial progress" value={project.financial_progress_pct} kind="percent" /><Fact label="Recorded completion" value={project.completion_recorded} /></dl></Section>

    <Section id="monitoring-health" title="2. Monitoring Health" subtitle="Compact status routing; select a tile to inspect its evidence."><div className="monitoring-health">{d.monitoring_health.map((item) => <a key={String(item.label)} href={`#${item.target}`}><span>{text(item.label)}</span><StatusPill value={item.status} /></a>)}</div></Section>

    <Section id="anomalies-irregularities" title="3. Anomalies & Irregularities" subtitle="Observed operational conditions remain distinct from statistical context."><div className="anomaly-grid">{d.anomalies_irregularities.map((item, index) => <article className={`anomaly-card ${index === d.anomalies_irregularities.length - 1 && d.anomalies_irregularities.length % 2 ? "anomaly-wide" : ""}`} key={`${item.title}-${index}`}><StatusPill value={item.status} /><h3>{text(item.title)}</h3><p>{text(item.value)}</p></article>)}</div><Technical><pre>{JSON.stringify(d.technical_details.anomaly, null, 2)}</pre></Technical></Section>

    <Section id="key-risk-areas" title="4. Key Risk Areas" subtitle="Expand a card for full structured evidence. Cards are independent; they are not separate verdicts."><div className="risk-grid">
      <RiskCard title="Fund Utilization & Payments" status={funds.status}><dl className="risk-facts"><Fact label="Sanctioned" value={funds.sanctioned_amount_inr} kind="money" /><Fact label="Released" value={funds.released_amount_inr} kind="money" /><Fact label="Recorded expenditure" value={funds.recorded_expenditure_inr} kind="money" /><Fact label="Released above sanction" value={funds.release_above_sanction_pct} kind="percent" /><Fact label="Financial / physical gap" value={funds.financial_physical_gap_pct} kind="percent" /><Fact label="Payment count" value={funds.payment_count} /></dl>{asRows(funds.evidence).length > 0 && <div className="table-wrap"><table><thead><tr><th>Release</th><th>Stage</th><th>Amount</th><th>Request</th><th>Authorization</th></tr></thead><tbody>{asRows(funds.evidence).map((row) => <tr key={String(row.payment_id)}><td>{text(row.payment_release_date)}</td><td>{text(row.payment_stage)}</td><td>{money(row.payment_amount_inr)}</td><td>{text(row.payment_request_date)}</td><td>{text(row.authorization_date)}</td></tr>)}</tbody></table></div>}</RiskCard>
      <RiskCard title="Delay & Schedule" status={delays.status}><dl className="risk-facts"><Fact label="Expected start" value={delays.expected_start} /><Fact label="Actual start" value={delays.actual_start} /><Fact label="Expected completion" value={delays.expected_completion} /><Fact label="Recorded completion" value={delays.recorded_completion} /></dl><p>Delay is shown as an observed schedule condition. No delay prediction model is fabricated.</p></RiskCard>
      <RiskCard title="Cost Overrun" status={cost.observed_status}><dl className="risk-facts"><Fact label="Observed condition" value={cost.observed_status} /><Fact label="Early-warning status" value={cost.early_warning_status} /><Fact label="Model quality" value={costTechnical.quality} /><Fact label="Evaluation label" value={costTechnical.evaluation_label} /></dl><p>Observed expenditure above sanction and model-estimated early warning are shown separately.</p><Technical><pre>{JSON.stringify(costTechnical, null, 2)}</pre></Technical></RiskCard>
      <RiskCard title="Duplicate Works" status={duplicate.status}>{asRows(duplicate.candidates).length ? asRows(duplicate.candidates).map((row) => { const candidate = asRecord(row.candidate_work); return <article className="duplicate-comparison" key={String(candidate.work_id)}><div><strong>{workId}</strong><p>{text(header.project_title)}</p></div><div><strong><Link className="work-link" href={`/works/${candidate.work_id}`}>{text(candidate.work_id)}</Link></strong><p>{text(candidate.work_description)}</p><small>{text(candidate.village)}, {text(candidate.district)}</small></div><dl><Fact label="Semantic similarity" value={numeric(Number(row.semantic_similarity_0_1) * 100, "%")} /><Fact label="Amount similarity" value={numeric(Number(row.amount_similarity_0_1) * 100, "%")} /><Fact label="Location distance" value={numeric(row.location_distance_metres, " m")} /></dl></article>; }) : <EmptyState label="No corroborated duplicate-work candidate is currently recorded." />}<p>{text(duplicate.disclaimer)}</p><Technical><pre>{JSON.stringify(duplicate.technical, null, 2)}</pre></Technical></RiskCard>
    </div></Section>

    <Section id="progress-schedule" title="5. Progress & Schedule" subtitle={text(d.progress_schedule.chronology)}><div className="serpentine-timeline">{timeline.map((event, index) => <article key={`${event.label}-${event.date}`} className={index % 2 ? "timeline-reverse" : ""}><div className="timeline-node"><span>{index + 1}</span></div><div><strong>{text(event.label)}</strong><time>{text(event.date)}</time><small>{text(event.kind)}</small></div></article>)}</div>{Object.keys(latestProgress).length > 0 && <dl className="latest-progress"><Fact label="Latest report" value={latestProgress.report_date} /><Fact label="Physical progress" value={latestProgress.physical_progress_pct} kind="percent" /><Fact label="Financial progress" value={latestProgress.financial_progress_pct} kind="percent" /><Fact label="Expected progress" value={latestProgress.expected_progress_pct_by_date} kind="percent" /></dl>}</Section>

    <Section id="geo-evidence" title="6. Geo-Tagged Progress Evidence" subtitle={text(geo.prototype_rule)}><div className="geo-summary"><Fact label="Current-month evidence" value={geoSummary.current_month_status} /><Fact label="Latest capture" value={geoSummary.latest_capture} /><Fact label="Location check" value={geoSummary.location_status} /><Fact label="Latest physical progress" value={geoSummary.latest_physical_progress_pct} kind="percent" /><Fact label="Late evidence entries" value={geoSummary.late_evidence_count} /><Fact label="Review Priority points" value={geoSummary.warning_contribution_points} /></div><GeoEvidenceActions workId={workId} items={geoItems} />
      {geoItems.length ? <div className="geo-gallery">{geoItems.map((item) => <article key={String(item.evidence_id)}><Image src={api.imageUrl(item.image_url, scope)} alt={`Synthetic demonstration site evidence for ${workId}`} width={420} height={250} unoptimized /><div><StatusPill value={item.window_status} /><StatusPill value={item.location_status} /><h3>{text(item.evidence_stage).replaceAll("_", " ")}</h3><p><MapPin size={14} />{numeric(item.latitude)}, {numeric(item.longitude)} · {numeric(item.physical_progress_pct, "%")} physical progress</p><small>{text(item.capture_timestamp)} · {text(item.source_type).replaceAll("_", " ")} · hash {text(item.image_sha256).slice(0, 12)}…</small></div></article>)}</div> : <EmptyState label="No site evidence is recorded for this work." />}<p className="section-note">{text(geo.integrity_note)}</p></Section>

    <Section id="records-completion" title="7. Records & Completion Readiness" subtitle={`Lifecycle: ${text(records.lifecycle)} · readiness: ${text(records.completion_readiness).replaceAll("_", " ")}`}><div className="record-status-grid">{Object.entries(recordStatuses).map(([label, value]) => <article key={label}><span>{friendlyEvidence(label)}</span><StatusPill value={value == null ? "Not recorded" : value} /></article>)}</div>{recordRows.length > 0 && <details className="secondary-context"><summary>View {recordRows.length} append-only record entries</summary><div className="table-wrap"><table><thead><tr><th>Type</th><th>Status</th><th>Date</th><th>Verification</th></tr></thead><tbody>{recordRows.map((row) => <tr key={String(row.record_id)}><td>{friendlyEvidence(row.record_type)}</td><td>{text(row.status)}</td><td>{text(row.record_date)}</td><td>{text(row.verification_status)}</td></tr>)}</tbody></table></div></details>}</Section>

    <Section id="ai-explanation" title="8. AI-Assisted Case Explanation" subtitle="The deterministic local explanation is always available; Groq is explicit-action-only."><div className="explanation-mode"><StatusPill value={explanationMode} /><span>Provider: {generated ? text(explain.data?.provider) : "Local deterministic fallback"}</span></div><Explanation value={generated ?? baseExplanation} /><ReviewDisclaimer /><div className="brief-actions"><button className="button" onClick={() => explain.mutate()} disabled={explain.isPending}><Bot size={15} />{explain.isPending ? "Preparing grounded explanation…" : "Generate Grounded AI Explanation"}</button><a className="button secondary" href={api.caseReportUrl(workId, scope)}><Download size={15} />Download nine-section case report</a></div>{explain.error && <p className="inline-error" role="alert">Groq could not be used. The deterministic explanation above remains authoritative for this prototype. {explain.error.message}</p>}<Technical><p>Model: {text(d.ai_explanation.model)} · method: {text(d.ai_explanation.method)} · fallback: {text(d.ai_explanation.fallback)}</p></Technical></Section>

    <Section id="officer-review" title="9. Officer Review & Corrective Action" subtitle={`Current case status: ${text(officer.current_status)}`}><form className="form-grid" onSubmit={submitReview}><label>Officer / desk label<input required minLength={2} maxLength={120} value={actor} onChange={(event) => setActor(event.target.value)} /></label><label>Case status<select value={status} onChange={(event) => setStatus(event.target.value)}>{["OPEN", "IN_REVIEW", "NEEDS_CLARIFICATION", "ESCALATED", "RESOLVED", "FALSE_POSITIVE"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="wide">Controlled follow-up action<select required value={action} onChange={(event) => setAction(event.target.value)}>{Object.entries(FOLLOW_UP_ACTION_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label className="wide">Officer note<textarea required minLength={2} maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} /></label><div className="wide"><button className="button" disabled={review.isPending}><FileCheck2 size={15} />{review.isPending ? "Recording…" : "Save append-only review"}</button>{review.isSuccess && <span className="success-inline" role="status"><CheckCircle2 size={14} />Review and audit event recorded.</span>}{review.error && <p className="inline-error" role="alert">{review.error.message}</p>}</div></form><ReviewDisclaimer /><div className="history-block"><h3>Append-only audit history</h3>{reviews.length ? reviews.map((row, index) => <article className="record-card" key={String(row.review_id ?? index)}><div className="record-card-head"><strong>{text(row.status).replaceAll("_", " ")}</strong><span>{text(row.created_at)}</span></div><p><strong>Follow-up:</strong> {FOLLOW_UP_ACTION_LABELS[text(row.follow_up_action)] ?? text(row.follow_up_action)}</p><p>{text(row.note)}</p><small>{text(row.actor_label)} · {text(row.actor_role)} · {text(row.scope_label)}</small></article>) : <EmptyState label="No officer review has been recorded yet." />}</div></Section>
  </>;
}
