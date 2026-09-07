"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronRight, Download, FileCheck2, MapPin, ShieldCheck, Sparkles } from "lucide-react";
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
  ["overview", "Overview"], ["payments-progress", "Payments & Progress"],
  ["compliance", "Compliance"], ["similar-works", "Similar Works"],
  ["documents-photos", "Documents & Photos"], ["alerts", "Alerts"],
  ["area-trend", "Area Trend"], ["case-summary", "Case Summary"],
  ["review-action", "Review & Action"], ["activity", "Activity"],
] as const;

function bool(value: unknown) { return value === true || String(value).toLowerCase() === "true"; }
function money(value: unknown) { const parsed = Number(value); return Number.isFinite(parsed) ? inr.format(parsed) : "Not available"; }
function numeric(value: unknown, suffix = "") { const parsed = Number(value); return Number.isFinite(parsed) ? `${number.format(parsed)}${suffix}` : "Not available"; }
function statusClass(value: unknown) {
  const status = String(value ?? "").toLowerCase();
  if (status.includes("non_compliant") || status.includes("very high") || status.includes("critical")) return "strong";
  if (status.includes("normal") || status.includes("good") || status.includes("recorded") || status.includes("pass")) return "ok";
  if (status.includes("review") || status.includes("delay") || status.includes("overrun") || status.includes("overdue") || status.includes("high")) return "review";
  return "neutral";
}
function chronologyIssue(row: Row) {
  const request = text(row.payment_request_date, ""); const authorization = text(row.authorization_date, "");
  return Boolean(request && authorization && authorization < request);
}
function evidenceSourceLabel(value: unknown) { return String(value).includes("UPLOAD") ? "Uploaded image" : "Site evidence"; }

function StatusPill({ value }: { value: unknown }) { return <span className={`dossier-status status-${statusClass(value)}`}>{text(value).replaceAll("_", " ")}</span>; }
function Fact({ label, value, kind, warning = false, attention = false, reason }: { label: string; value: unknown; kind?: "money" | "percent"; warning?: boolean; attention?: boolean; reason?: string }) {
  const rendered = kind === "money" ? money(value) : kind === "percent" ? numeric(value, "%") : text(value);
  return <div className={`dossier-fact ${warning ? "dossier-fact-warning" : attention ? "dossier-fact-attention" : ""}`}><dt>{(warning || attention) && <AlertTriangle size={11} />}{label}</dt><dd>{rendered}</dd>{reason && <small className="field-reason">{reason}</small>}</div>;
}
function RiskCard({ title, status, children }: { title: string; status: unknown; children: ReactNode }) {
  return <details className={`risk-card risk-${statusClass(status)}`}><summary><span><strong>{title}</strong><StatusPill value={status} /></span><ChevronRight size={18} aria-hidden="true" /></summary><div className="risk-card-body">{children}</div></details>;
}
function ReviewDisclaimer() {
  return <div className="review-note"><ShieldCheck size={18} /><div><strong>Authorized human review remains final</strong><p>This platform organizes evidence for verification. It does not establish wrongdoing, liability or an official decision.</p></div></div>;
}
function Explanation({ value }: { value: Row }) {
  const why = asRows(value.why_flagged); const issues = Array.isArray(value.main_issues) ? value.main_issues : [];
  return <div className="explanation-body"><p className="explanation-summary">{text(value.summary ?? value.what_the_work_is, "A case summary is available from the recorded evidence.")}</p>
    {Array.isArray(value.what_happened) && <div><h3>What happened</h3><ul>{value.what_happened.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul></div>}
    {!!issues.length && <div><h3>Main issues</h3><ul>{issues.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul></div>}
    {!!why.length && <div><h3>Why this work needs attention</h3>{why.map((row, index) => <article className="explanation-evidence" key={`${row.family}-${index}`}><strong>{friendlyEvidence(row.family)}</strong><p>{text(row.finding)}</p><small>{text(row.interpretation)}</small></article>)}</div>}
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
  if (query.isLoading) return <LoadingState label="Loading work details…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;

  const d = query.data; const header = d.header; const project = d.project_details;
  const risks = d.key_risk_areas; const funds = asRecord(risks.fund_utilization); const delays = asRecord(risks.delays);
  const cost = asRecord(risks.cost_overrun); const duplicate = asRecord(risks.duplicate_works);
  const payments = asRows(funds.evidence); const timeline = asRows(d.progress_schedule.timeline); const latestProgress = asRecord(d.progress_schedule.latest_progress);
  const geo = d.geo_evidence; const geoSummary = asRecord(geo.summary); const geoItems = asRows(geo.items);
  const records = d.records_completion; const recordStatuses = asRecord(records.statuses); const recordRows = asRows(records.records);
  const officer = d.officer_review; const reviews = asRows(officer.reviews);
  const baseExplanation = asRecord(d.ai_explanation.explanation); const generated = explain.data ? asRecord(explain.data.explanation) : null;
  const releaseWarning = bool(asRecord(project.field_highlights).released_payments_inr);
  const gap = Number(funds.financial_physical_gap_pct); const gapWarning = Number.isFinite(gap) && Math.abs(gap) >= 25;
  const delayWarning = ["review", "strong"].includes(statusClass(delays.status));
  const attentionAreas = [
    releaseWarning && { label: "Payments", target: "payments-progress" },
    gapWarning && { label: "Progress", target: "payments-progress" },
    delayWarning && { label: "Schedule", target: "payments-progress" },
    text(records.completion_readiness).includes("REVIEW") && { label: "Compliance", target: "compliance" },
    asRows(duplicate.candidates).length > 0 && { label: "Similar Works", target: "similar-works" },
  ].filter(Boolean) as { label: string; target: string }[];

  return <>
    <header className="dossier-header"><div><p className="eyebrow">{text(header.workspace, "Work Monitoring")}</p><h1>{text(header.project_title)}</h1><p><strong>{workId}</strong> · {text(header.location)}</p></div><div className="dossier-priority"><span>Review Priority</span><strong>{numeric(header.review_priority_score_0_100)}</strong><StatusPill value={header.attention_level} /></div></header>
    {attentionAreas.length > 0 && <div className="attention-strip"><AlertTriangle size={18} /><strong>Needs Attention</strong>{attentionAreas.map((item) => <a key={`${item.target}-${item.label}`} href={`#${item.target}`}>{item.label}</a>)}</div>}
    <nav className="section-nav dossier-nav" aria-label="Work sections">{SECTION_LINKS.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav>

    <Section id="overview" title="Overview" subtitle="Recorded work and location details."><dl className="dossier-facts"><Fact label="Work ID" value={project.work_id} /><Fact label="Lifecycle" value={project.lifecycle} /><Fact label="Work status" value={project.recorded_work_status} /><Fact label="Officer status" value={project.officer_case_status} /><Fact label="Member of Parliament" value={project.member_of_parliament} /><Fact label="Constituency" value={project.constituency} /><Fact label="Location" value={project.location} /><Fact label="Sanctioned amount" value={project.sanctioned_amount_inr} kind="money" /><Fact label="Released payments" value={project.released_payments_inr} kind="money" warning={releaseWarning} reason={releaseWarning ? `${money(funds.difference_inr)} above sanctioned cost` : undefined} /><Fact label="Physical progress" value={project.physical_progress_pct} kind="percent" attention={gapWarning} reason={gapWarning ? `${numeric(Math.abs(gap))} percentage point gap` : undefined} /><Fact label="Financial progress" value={project.financial_progress_pct} kind="percent" attention={gapWarning} reason={gapWarning ? `${numeric(Math.abs(gap))} percentage point gap` : undefined} /><Fact label="Completion recorded" value={project.completion_recorded} /></dl></Section>

    <Section id="payments-progress" title="Payments & Progress" subtitle="Payment chronology, expenditure and recorded progress remain separate evidence streams."><div className="risk-grid"><RiskCard title="Fund Utilization & Payments" status={funds.status}><dl className="risk-facts"><Fact label="Sanctioned" value={funds.sanctioned_amount_inr} kind="money" /><Fact label="Released" value={funds.released_amount_inr} kind="money" warning={releaseWarning} reason={releaseWarning ? `${money(funds.difference_inr)} above sanctioned cost` : undefined} /><Fact label="Recorded expenditure" value={funds.recorded_expenditure_inr} kind="money" /><Fact label="Released above sanction" value={funds.release_above_sanction_pct} kind="percent" warning={releaseWarning} /><Fact label="Financial / physical gap" value={funds.financial_physical_gap_pct} kind="percent" attention={gapWarning} reason={gapWarning ? `${numeric(Math.abs(gap))} percentage point gap` : undefined} /><Fact label="Payment entries" value={funds.payment_count} /></dl>{payments.length > 0 && <div className="table-wrap"><table><thead><tr><th>Release</th><th>Stage</th><th>Amount</th><th>Request</th><th>Authorization</th></tr></thead><tbody>{payments.map((row) => { const outOfOrder = chronologyIssue(row); return <tr className={outOfOrder ? "field-row-warning" : ""} key={String(row.payment_id)}><td>{text(row.payment_release_date)}</td><td>{text(row.payment_stage)}</td><td>{money(row.payment_amount_inr)}</td><td>{text(row.payment_request_date)}</td><td>{text(row.authorization_date)}{outOfOrder && <small className="field-reason">Authorization predates request</small>}</td></tr>; })}</tbody></table></div>}</RiskCard>
      <RiskCard title="Schedule" status={delays.status}><dl className="risk-facts"><Fact label="Expected start" value={delays.expected_start} /><Fact label="Actual start" value={delays.actual_start} /><Fact label="Expected completion" value={delays.expected_completion} warning={delayWarning} reason={delayWarning && Number(delays.overdue_days) > 0 ? `Overdue by ${numeric(delays.overdue_days)} days` : undefined} /><Fact label="Recorded completion" value={delays.recorded_completion} /></dl><p>Schedule attention is based on recorded dates and current work status.</p></RiskCard></div>
      <div className="serpentine-timeline">{timeline.map((event, index) => <article key={`${event.label}-${event.date}`}><div className="timeline-node"><span>{index + 1}</span></div><div><strong>{text(event.label)}</strong><time>{text(event.date)}</time><small>{text(event.kind)}</small></div></article>)}</div>{Object.keys(latestProgress).length > 0 && <dl className="latest-progress"><Fact label="Latest report" value={latestProgress.report_date} /><Fact label="Physical progress" value={latestProgress.physical_progress_pct} kind="percent" /><Fact label="Financial progress" value={latestProgress.financial_progress_pct} kind="percent" /><Fact label="Expected progress" value={latestProgress.expected_progress_pct_by_date} kind="percent" /></dl>}
    </Section>

    <Section id="compliance" title="Compliance" subtitle={`Completion readiness: ${text(records.completion_readiness).replaceAll("_", " ")}`}><div className="record-status-grid">{Object.entries(recordStatuses).map(([label, value]) => <article key={label}><span>{friendlyEvidence(label)}</span><StatusPill value={value == null ? "Not applicable" : value} /></article>)}</div>{recordRows.length > 0 && <details className="secondary-context"><summary>View {recordRows.length} record entries</summary><div className="table-wrap"><table><thead><tr><th>Type</th><th>Status</th><th>Date</th><th>Verification</th></tr></thead><tbody>{recordRows.map((row) => <tr key={String(row.record_id)}><td>{friendlyEvidence(row.record_type)}</td><td>{text(row.status)}</td><td>{text(row.record_date)}</td><td>{text(row.verification_status)}</td></tr>)}</tbody></table></div></details>}</Section>

    <Section id="similar-works" title="Similar Works" subtitle="Potential matches are review leads, not confirmed duplicates.">{asRows(duplicate.candidates).length ? <div className="similar-work-list">{asRows(duplicate.candidates).map((row) => { const candidate = asRecord(row.candidate_work); return <article className="duplicate-comparison" key={String(candidate.work_id)}><div><strong>{workId}</strong><p>{text(header.project_title)}</p></div><div><strong><Link className="work-link" href={`/works/${candidate.work_id}`}>{text(candidate.work_id)}</Link></strong><p>{text(candidate.work_description)}</p><small>{text(candidate.village)}, {text(candidate.district)}</small></div><dl><Fact label="Description match" value={numeric(Number(row.semantic_similarity_0_1) * 100, "%")} /><Fact label="Cost match" value={numeric(Number(row.amount_similarity_0_1) * 100, "%")} /><Fact label="Location distance" value={numeric(row.location_distance_metres, " m")} /></dl></article>; })}</div> : <EmptyState label="No similar work requiring review is currently recorded." />}<p className="section-note">{text(duplicate.disclaimer)}</p></Section>

    <Section id="documents-photos" title="Documents & Photos" subtitle="Site evidence, recorded location and document readiness."><div className="geo-summary"><Fact label="Current-month evidence" value={geoSummary.current_month_status} /><Fact label="Latest capture" value={geoSummary.latest_capture} /><Fact label="Location check" value={geoSummary.location_status} /><Fact label="Latest physical progress" value={geoSummary.latest_physical_progress_pct} kind="percent" /><Fact label="Late evidence entries" value={geoSummary.late_evidence_count} /></div><GeoEvidenceActions workId={workId} items={geoItems} />
      {geoItems.length ? <div className="geo-gallery">{geoItems.map((item) => <article key={String(item.evidence_id)}><Image src={api.imageUrl(item.image_url, scope)} alt={`Site evidence for ${workId}`} width={420} height={250} unoptimized /><div><StatusPill value={item.window_status} /><StatusPill value={item.location_status} /><h3>{text(item.evidence_stage).replaceAll("_", " ")}</h3><p><MapPin size={14} />{numeric(item.latitude)}, {numeric(item.longitude)} · {numeric(item.physical_progress_pct, "%")} physical progress</p><small>{text(item.capture_timestamp)} · {evidenceSourceLabel(item.source_type)}</small></div></article>)}</div> : <EmptyState label="No site evidence is recorded for this work." />}<p className="section-note">Location matches indicate recorded proximity only; they do not prove when or where an image was originally captured.</p></Section>

    <Section id="alerts" title="Alerts" subtitle="Recorded conditions and review signals that may need verification."><div className="monitoring-health">{d.monitoring_health.map((item) => <div key={String(item.label)}><span>{text(item.label)}</span><StatusPill value={item.status} /></div>)}</div><div className="anomaly-grid">{d.anomalies_irregularities.map((item, index) => <article className={`anomaly-card ${index === d.anomalies_irregularities.length - 1 && d.anomalies_irregularities.length % 2 ? "anomaly-wide" : ""}`} key={`${item.title}-${index}`}><StatusPill value={item.status} /><h3>{text(item.title)}</h3><p>{text(item.value)}</p></article>)}</div><div className="risk-grid compact-risk-grid"><RiskCard title="Cost Alert" status={cost.observed_status}><dl className="risk-facts"><Fact label="Observed condition" value={cost.observed_status} /><Fact label="Early warning" value={cost.early_warning_status} /></dl><p>Observed spending and forward-looking warning evidence are shown separately.</p></RiskCard><RiskCard title="Similar Work Review" status={duplicate.status}><p>{text(duplicate.disclaimer)}</p></RiskCard></div></Section>

    <Section id="area-trend" title="Area Trend" subtitle="Compare this work with delivery patterns in its wider authority scope."><div className="area-trend-callout"><div><strong>View area performance</strong><p>Use district, state and national comparisons to place this work in context. Area results never change this work&apos;s Review Priority.</p></div><Link className="button secondary" href="/trends">Open Area Trends</Link></div></Section>

    <Section id="case-summary" title="Case Summary" subtitle="A concise explanation of the recorded evidence and recommended checks."><Explanation value={generated ?? baseExplanation} /><ReviewDisclaimer /><div className="brief-actions"><button className="button" onClick={() => explain.mutate()} disabled={explain.isPending}><Sparkles size={15} />{explain.isPending ? "Preparing summary…" : "Explain This Case"}</button><a className="button secondary" href={api.caseReportUrl(workId, scope)}><Download size={15} />Download Case Report</a></div>{explain.error && <p className="inline-error" role="alert">Case summary could not be refreshed. The current summary remains available.</p>}</Section>

    <Section id="review-action" title="Review & Action" subtitle={`Current status: ${text(officer.current_status).replaceAll("_", " ")}`}><form className="form-grid" onSubmit={submitReview}><label>Officer / desk label<input required minLength={2} maxLength={120} value={actor} onChange={(event) => setActor(event.target.value)} /></label><label>Case status<select value={status} onChange={(event) => setStatus(event.target.value)}>{["OPEN", "IN_REVIEW", "NEEDS_CLARIFICATION", "ESCALATED", "RESOLVED", "FALSE_POSITIVE"].map((item) => <option value={item} key={item}>{item.replaceAll("_", " ")}</option>)}</select></label><label className="wide">Follow-up action<select required value={action} onChange={(event) => setAction(event.target.value)}>{Object.entries(FOLLOW_UP_ACTION_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label className="wide">Officer note<textarea required minLength={2} maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} /></label><div className="wide"><button className="button" disabled={review.isPending}><FileCheck2 size={15} />{review.isPending ? "Recording…" : "Save Review"}</button>{review.isSuccess && <span className="success-inline" role="status"><CheckCircle2 size={14} />Review and activity event recorded.</span>}{review.error && <p className="inline-error" role="alert">{review.error.message}</p>}</div></form><ReviewDisclaimer /></Section>

    <Section id="activity" title="Activity" subtitle="Append-only officer review history."><div className="history-block">{reviews.length ? reviews.map((row, index) => <article className="record-card" key={String(row.review_id ?? index)}><div className="record-card-head"><strong>{text(row.status).replaceAll("_", " ")}</strong><span>{text(row.created_at)}</span></div><p><strong>Follow-up:</strong> {FOLLOW_UP_ACTION_LABELS[text(row.follow_up_action)] ?? text(row.follow_up_action)}</p><p>{text(row.note)}</p><small>{text(row.actor_label)} · {text(row.actor_role)} · {text(row.scope_label)}</small></article>) : <EmptyState label="No officer review has been recorded yet." />}</div></Section>
  </>;
}
