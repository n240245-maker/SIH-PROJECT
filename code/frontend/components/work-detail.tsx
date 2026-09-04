"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, BarChart3, Bot, CheckCircle2, ChevronRight, Download,
  FileCheck2, Info, MinusCircle, ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, ReactNode, useState } from "react";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { boolLabel, number, text } from "@/lib/format";
import {
  Row, asRecord, asRows, attentionLabel, complianceState, documentStateLabel,
  familyLabel, FOLLOW_UP_ACTION_LABELS, formatFact, formatMetric, humanizeNarrative,
  metricLabel, readinessGroup,
} from "@/lib/presentation";
import { useScope } from "@/lib/scope";

const SECTION_LINKS = [
  ["overview", "Case Overview"], ["attention", "Why Attention"],
  ["warnings", "Warnings"], ["payments", "Fund Utilization"],
  ["timeline", "Progress & Schedule"], ["readiness", "Records"],
  ["compliance", "Compliance"], ["duplicates", "Duplicate Review"],
  ["peer", "Similar Works"], ["forecast", "Forecast"],
  ["brief", "AI Explanation"], ["review", "Officer Action"],
] as const;

const STATE_LABELS: Record<string, string> = {
  strong_issue: "High Attention", review: "Requires Review",
  analytical: "Analytical Signal", context: "Information", pass: "Normal",
  not_applicable: "Not Applicable", insufficient: "Insufficient Data",
};

const ACTIONABLE_TYPES = new Set([
  "COMPLIANCE_REVIEW", "DETERMINISTIC_NON_COMPLIANCE", "DUPLICATE_REVIEW_CANDIDATE",
  "FUND_PROGRESS_REVIEW", "OBSERVED_OVERDUE", "OBSERVED_OVER_SANCTION", "PAYMENT_IRREGULARITY",
]);

function StatePill({ state, label }: { state: string; label?: string }) {
  const rendered = label ?? STATE_LABELS[state] ?? state;
  const Icon = state === "strong_issue" ? ShieldAlert
    : state === "pass" ? CheckCircle2
    : state === "analytical" ? BarChart3
    : state === "not_applicable" ? MinusCircle
    : state === "context" || state === "insufficient" ? Info
    : AlertTriangle;
  return <span className={`state-pill state-${state}`} aria-label={`Status: ${rendered}`}><Icon size={12} aria-hidden="true" />{rendered}</span>;
}

function WorkBand({ value }: { value: unknown }) {
  const band = String(value ?? "UNKNOWN");
  return <span className={`band band-${band.toLowerCase()}`}>{band}</span>;
}

function TechnicalDetails({ children, label = "Technical details" }: { children: ReactNode; label?: string }) {
  return <details className="technical-details"><summary aria-label={`Expand ${label.toLowerCase()}`}>{label}</summary><div>{children}</div></details>;
}

function Field({ label, value, format, suffix, highlight }: {
  label: string; value: unknown; format?: "currency" | "percent" | "percentage_points" | "date";
  suffix?: string; highlight?: Row;
}) {
  const rendered = format ? formatFact(value, format)
    : typeof value === "boolean" ? boolLabel(value)
    : typeof value === "number" ? number.format(value)
    : `${text(value)}${value !== null && value !== undefined && value !== "" ? suffix ?? "" : ""}`;
  const state = String(highlight?.state ?? "");
  return <div className={`profile-field ${state ? `field-${state}` : ""}`}><dt>{label}</dt><dd>{rendered}</dd>{state && <small><StatePill state={state} label={text(highlight?.label, text(highlight?.reason))} /></small>}</div>;
}

function ReviewNote() {
  return <div className="review-note"><strong>Human review remains authoritative</strong><p>This explanation summarizes recorded facts, deterministic MPLADS checks, and analytical signals. It does not establish wrongdoing or replace verification of authoritative records.</p></div>;
}

function ProgressComparison({ physical, financial }: { physical: number | null; financial: number | null }) {
  if (physical === null || financial === null) return <EmptyState label="No paired physical and financial progress values are available." />;
  const scale = Math.max(100, Math.ceil(Math.max(physical, financial) / 20) * 20);
  return <div className="progress-comparison" aria-label="Physical and financial progress comparison">
    <div className="progress-scale"><span>0%</span><span>Shared scale: {scale}%</span></div>
    {[["Physical progress", physical, "physical"], ["Financial progress", financial, "financial"]].map(([label, value, kind]) => <div className="progress-line" key={String(kind)}><div className="progress-label"><span>{label}</span><strong>{number.format(Number(value))}%</strong></div><div className="progress-track"><span className={`progress-fill progress-${kind}`} style={{ width: `${Math.max(0, Number(value) / scale * 100)}%` }} /></div></div>)}
  </div>;
}

function ReadinessRows({ readiness }: { readiness: Row }) {
  const entries = asRows(readiness.entries);
  const groups = ["Recorded", "Requires Review", "Not Recorded", "Not Applicable"] as const;
  return <div className="readiness-groups">{groups.map((group) => {
    const rows = entries.filter((row) => readinessGroup(row.status_code) === group);
    if (!rows.length) return null;
    return <section className="readiness-group" key={group}><h3>{group} <span>· {rows.length}</span></h3><div className="compact-row-list">{rows.map((row) => <details className={`expandable-row state-border-${text(row.state)}`} key={text(row.key)}><summary aria-label={`Expand ${text(row.label)} details`}><span className="compact-row-main"><strong>{text(row.label)}</strong><small>{documentStateLabel(row.status_code)}</small></span><StatePill state={text(row.state)} label={text(row.status_label)} /><ChevronRight className="disclosure-icon" size={16} aria-hidden="true" /></summary><div className="row-detail"><dl className="data-list"><Field label="Observed" value={row.observed ?? row.source_value} /><Field label="Snapshot interpretation" value={row.status_label} /></dl><TechnicalDetails><p>Rule <code>{text(row.rule_id)}</code> · result <code>{text(row.rule_result)}</code> · source value <code>{text(row.source_value)}</code></p></TechnicalDetails></div></details>)}</div></section>;
  })}</div>;
}

function ComplianceRow({ rule }: { rule: Row }) {
  const state = complianceState(rule.result);
  const label = text(rule.result) === "NON_COMPLIANT" ? "Non-Compliant" : text(rule.result) === "REVIEW" ? "Requires Review" : text(rule.result).replaceAll("_", " ");
  return <details className={`expandable-row state-border-${state}`}><summary aria-label={`Expand ${text(rule.rule_title)} rule details`}><span className="compact-row-main"><strong>{text(rule.rule_title)}</strong><small>{text(rule.observed_value)}</small></span><StatePill state={state} label={label} /><ChevronRight className="disclosure-icon" size={16} /></summary><div className="row-detail"><dl className="data-list"><Field label="Observed" value={rule.observed_value} /><Field label="Expected" value={rule.expected_condition} /></dl><p>{text(rule.evidence)}</p><div className="citation">MPLADS clause {text(rule.guideline_clause)} · page {text(rule.guideline_page)}</div><TechnicalDetails><p>Rule <code>{text(rule.rule_id)}</code> · chunk <code>{text(rule.guideline_chunk_ids)}</code> · source <code>{text(rule.source_artifact)}</code></p></TechnicalDetails></div></details>;
}

function Explanation({ assessment, narrative, generated }: { assessment: Row; narrative: Row; generated: boolean }) {
  const project = asRecord(assessment.project);
  const observations = asRows(assessment.main_observations);
  const grounded = asRows(narrative.why_flagged);
  const issues = generated && grounded.length
    ? grounded.slice(0, 3).map((item) => humanizeNarrative(item.finding))
    : observations.slice(0, 3).map((item) => text(item.summary));
  return <div className="plain-explanation">
    <section><h3>About this work</h3><p>{text(project.work_title)} is a {text(project.lifecycle).replaceAll("_", " ").toLowerCase()}-stage work in {text(project.location)}.</p></section>
    <section><h3>What happened</h3><p>{generated && narrative.summary ? humanizeNarrative(narrative.summary) : text(assessment.executive_summary)}</p></section>
    <section><h3>Main issues</h3>{issues.length ? <ul>{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : <p>No current governed issue requires an AI-generated interpretation.</p>}</section>
  </div>;
}

export default function WorkDetail() {
  const { workId } = useParams<{ workId: string }>();
  const { scope } = useScope();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["work", workId], queryFn: () => api.work(workId) });
  const [explanation, setExplanation] = useState<Row | null>(null);
  const explain = useMutation({ mutationFn: () => api.explain(workId, true), onSuccess: setExplanation });
  const review = useMutation({ mutationFn: (payload: Record<string, string>) => api.addReview(workId, payload), onSuccess: () => client.invalidateQueries({ queryKey: ["work", workId] }) });
  const [status, setStatus] = useState("IN_REVIEW");
  const [action, setAction] = useState("REQUEST_CLARIFICATION");
  const [actor, setActor] = useState("");
  const [note, setNote] = useState("");

  if (query.isLoading) return <LoadingState label="Loading complete work dossier…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;

  const d = query.data;
  const p = d.profile;
  const priority = d.priority;
  const presentation = asRecord(d.presentation);
  const highlights = asRecord(presentation.highlighted_fields);
  const financial = asRecord(presentation.financial);
  const chronology = asRecord(presentation.payment_chronology);
  const timeline = asRecord(presentation.timeline);
  const readiness = asRecord(presentation.document_readiness);
  const trend = asRecord(presentation.trend);
  const assessment = asRecord(presentation.case_assessment);
  const peer = asRecord(d.peer_benchmark);
  const duplicates = asRecord(d.duplicates);
  const payments = asRecord(d.payments);
  const compliance = asRecord(d.compliance);
  const prediction = asRecord(d.prediction);
  const scores = asRecord(prediction.scores);
  const currentExplanation = explanation ?? asRecord(d.explanation);
  const narrative = asRecord(currentExplanation.explanation);
  const contributions = [...d.contributions].filter((row) => Number(row.contribution_points ?? 0) > 0).sort((a, b) => Number(b.contribution_points ?? 0) - Number(a.contribution_points ?? 0));
  const warnings = asRows(presentation.warning_signals);
  const actionableWarnings = warnings.filter((row) => ACTIONABLE_TYPES.has(text(asRecord(row.technical_reference).alert_type)));
  const rules = asRows(compliance.rules);
  const actionableRules = rules.filter((row) => ["NON_COMPLIANT", "REVIEW"].includes(String(row.result)));
  const ordinaryRules = rules.filter((row) => !["NON_COMPLIANT", "REVIEW"].includes(String(row.result)));
  const counts = asRecord(presentation.compliance_counts);
  const physical = typeof financial.physical_progress_pct === "number" ? financial.physical_progress_pct : null;
  const financialProgress = typeof financial.financial_progress_pct === "number" ? financial.financial_progress_pct : null;
  const mode = String(currentExplanation.generation_mode ?? "DETERMINISTIC_FALLBACK");
  const provider = String(currentExplanation.api_status ?? "OFFLINE_DEFAULT");
  const badge = mode === "GROQ_GROUNDED" ? "GROQ GROUNDED" : "LOCAL DETERMINISTIC FALLBACK";
  const scopeLabel = [scope.role, scope.state, scope.district, scope.mp_id].filter(Boolean).join(" · ");
  const submitReview = (event: FormEvent) => {
    event.preventDefault();
    review.mutate({ actor_role: scope.role, actor_label: actor, status, follow_up_action: action, scope_label: scopeLabel, note });
  };

  return <>
    <header className="case-header"><div><p className="eyebrow">Officer case workspace</p><h1>{text(p.work_description)}</h1><p>{workId} · {text(p.village)}, {text(p.block)}, {text(p.district)}, {text(p.state_name)}</p><span className={`attention-badge attention-${text(presentation.attention_level).toLowerCase()}`}>{attentionLabel(presentation.attention_level)}</span>{presentation.requires_review === true && <span className="requires-review">Requires Review</span>}</div><div className="priority-lockup"><span>Governed Review Priority</span><strong>{number.format(Number(priority.review_priority_score_0_100 ?? 0))}<small>/100</small></strong><WorkBand value={priority.review_priority_band} /></div></header>
    <div className="priority-disclaimer"><Info size={16} /><span>The score prioritizes review; it is not a probability of wrongdoing.</span></div>
    <nav className="section-nav" aria-label="Work detail sections">{SECTION_LINKS.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav>

    <Section id="overview" title="Case at a Glance" subtitle="The current project record and monitoring state">
      <div className="overview-grid"><div><h3>Main attention areas</h3><div className="attention-list">{(presentation.main_attention_areas as string[]).map((item) => <span key={item}><AlertTriangle size={14} />{item}</span>)}</div></div><dl className="case-facts"><Field label="Work ID" value={workId} /><Field label="Lifecycle" value={p.lifecycle_stage} /><Field label="Recorded work status" value={p.source_current_status} /><Field label="Officer case status" value={d.current_review_status} /></dl></div>
      <h3 className="subsection-title">Key context</h3><dl className="data-list key-context"><Field label="MP" value={`${text(p.mp_name)} (${text(p.mp_id)})`} /><Field label="Constituency" value={p.constituency} /><Field label="Location" value={`${text(p.village)}, ${text(p.block)}, ${text(p.district)}, ${text(p.state_name)}`} /><Field label="Lifecycle" value={p.lifecycle_stage} /><Field label="Sanctioned amount" value={p.sanctioned_amount_inr} format="currency" highlight={asRecord(highlights.sanctioned_amount_inr)} /><Field label="Released payments" value={p.released_payment_total_inr_as_of} format="currency" highlight={asRecord(highlights.released_payment_total_inr_as_of)} /><Field label="Physical progress" value={p.latest_physical_progress_pct_as_of} format="percent" /><Field label="Financial progress" value={p.latest_financial_progress_pct_as_of} format="percent" /><Field label="Completion recorded" value={p.completion_date_as_of} format="date" /><Field label="Duplicate-review candidate" value={asRows(duplicates.review_candidates).length ? text(asRecord(asRows(duplicates.review_candidates)[0].paired_work).work_id) : "None"} /></dl>
      <h3 className="subsection-title">Monitoring health</h3><div className="monitoring-grid">{asRows(presentation.monitoring_health).map((row) => <div className="monitoring-row" key={text(row.dimension)}><span>{text(row.dimension)}</span><StatePill state={text(row.state)} label={text(row.status)} /></div>)}</div>
      <TechnicalDetails label="View full source profile"><dl className="data-list">{Object.entries(p).map(([key, value]) => <Field key={key} label={key.replaceAll("_", " ")} value={value} />)}</dl></TechnicalDetails>
    </Section>

    <Section id="attention" title="Why This Work Needs Attention" subtitle="Strongest governed reasons, without calculation detail">
      <div className="score-explainer"><div className="score-ring"><strong>{number.format(Number(priority.review_priority_score_0_100))}</strong><span>of 100</span></div><div><h3>{attentionLabel(presentation.attention_level)}</h3><p>{actionableWarnings.length ? "This work has independent conditions requiring officer review." : "No current actionable review condition is present."}</p><p>The score prioritizes review; it is not a probability of wrongdoing.</p></div></div>
      {actionableWarnings.length ? <div className="reason-list">{actionableWarnings.slice(0, 5).map((row) => <div className={`reason-row state-border-${text(row.state)}`} key={text(asRecord(row.technical_reference).alert_type)}><StatePill state={text(row.state)} label={text(row.severity_label)} /><div><strong>{text(row.title)}</strong><p>{text(row.summary)}</p></div></div>)}</div> : <div className="normal-callout"><CheckCircle2 size={17} /><strong>Normal — no current actionable review condition is present.</strong></div>}
      <TechnicalDetails label="Exact Review Priority composition"><div className="technical-table" role="table" aria-label="Exact Review Priority composition">{contributions.map((row) => <div role="row" key={text(row.family)}><span role="cell">{familyLabel(row.family)}</span><strong role="cell">{text(row.contribution_points)} / {text(row.family_weight_pct)}</strong><small role="cell">{text(row.evidence_summary)}</small></div>)}</div><p>Exact total: <strong>{text(d.contribution_sum)}</strong></p></TechnicalDetails>
    </Section>

    <Section id="warnings" title="Warnings & Review Signals" subtitle="Current conditions and analytical context remain distinct">
      {warnings.length ? <div className="compact-row-list">{warnings.map((row, index) => <details className={`expandable-row state-border-${text(row.state)}`} key={`${text(row.title)}-${index}`}><summary aria-label={`Expand ${text(row.title)} details`}><StatePill state={text(row.state)} label={text(row.severity_label)} /><span className="compact-row-main"><strong>{text(row.title)}</strong><small>{text(row.summary)}</small></span><ChevronRight className="disclosure-icon" size={16} /></summary><div className="row-detail">{asRows(row.key_facts).length > 0 && <dl className="data-list">{asRows(row.key_facts).map((fact) => <Field key={text(fact.label)} label={text(fact.label)} value={formatFact(fact.value, fact.format)} />)}</dl>}<p><strong>Why it matters:</strong> {text(row.why_attention)}</p><p><strong>Officer verification:</strong> {text(row.officer_verification)}</p><TechnicalDetails><pre>{JSON.stringify(row.technical_reference, null, 2)}</pre></TechnicalDetails></div></details>)}</div> : <div className="normal-callout"><CheckCircle2 size={17} /><strong>Normal — no current review signal is present.</strong></div>}
    </Section>

    <Section id="payments" title="Fund Utilization & Payments" subtitle="Recorded financial facts and work progress remain separate">
      <div className={`fund-health state-border-${text(asRecord(financial.exceedance_display_severity).state)}`}><div><span>Fund Utilization Health</span><StatePill state={text(asRecord(financial.exceedance_display_severity).state)} label={text(asRecord(financial.exceedance_display_severity).label)} /></div><p>{text(financial.health_interpretation)}</p></div>
      <dl className="data-list financial-rows"><Field label="Estimated cost" value={financial.estimated_cost_inr} format="currency" /><Field label="Sanctioned amount" value={financial.sanctioned_amount_inr} format="currency" /><Field label="Released amount" value={financial.released_payments_inr} format="currency" /><Field label="Recorded expenditure" value={financial.recorded_expenditure_inr} format="currency" /><Field label="Financial progress" value={financial.financial_progress_pct} format="percent" /><Field label="Physical progress" value={financial.physical_progress_pct} format="percent" /><Field label="Finance vs physical gap" value={financial.financial_minus_physical_gap_percentage_points} format="percentage_points" /><Field label="Released vs sanction difference" value={financial.released_minus_sanction_inr} format="currency" /><Field label="Released above sanction" value={financial.percentage_above_sanction} format="percent" /><Field label="Payment count" value={p.released_payment_count_as_of} /></dl>
      <div className="payment-progress-grid"><ProgressComparison physical={physical} financial={financialProgress} /><div className="gap-card"><span>Financial minus physical gap</span><strong>{formatFact(financial.financial_minus_physical_gap_percentage_points, "percentage_points")}</strong>{financial.persistent_gap === true && <><StatePill state="review" label="Persistent mismatch" /><p>The mismatch appears across multiple consecutive progress reports.</p></>}</div></div>
      {chronology.authorization_before_request === true ? <details className="expandable-row state-border-review"><summary><StatePill state="review" /><span className="compact-row-main"><strong>Payment chronology needs verification</strong><small>Authorization {formatFact(chronology.authorization_date, "date")} · request {formatFact(chronology.request_date, "date")}</small></span><ChevronRight size={16} /></summary><div className="row-detail"><p>Verify the payment request, authorization order, and PFMS/source sequence.</p></div></details> : <div className="normal-callout"><CheckCircle2 size={17} /><strong>Normal — no payment chronology issue is currently flagged.</strong></div>}
      <TechnicalDetails label="Payment and fund-progress evidence"><pre>{JSON.stringify({ payment_evidence: payments.evidence, fund_progress: payments.fund_progress }, null, 2)}</pre></TechnicalDetails>
    </Section>

    <Section id="timeline" title="Progress & Schedule" subtitle="Recorded events and planned dates are clearly distinguished">
      <dl className="data-list"><Field label="Physical progress" value={financial.physical_progress_pct} format="percent" /><Field label="Financial progress" value={financial.financial_progress_pct} format="percent" /><Field label="Expected completion" value={p.expected_completion_date} format="date" highlight={asRecord(highlights.expected_completion_date)} /><Field label="Recorded completion" value={p.completion_date_as_of} format="date" /></dl>
      <div className="case-timeline">{asRows(timeline.events).map((event, index) => <article className={`timeline-event timeline-${text(event.state)}`} key={index}><time>{formatFact(event.date, "date")}</time><div className="timeline-marker">{event.state === "strong_issue" ? "▲" : event.state === "review" ? "◆" : event.kind === "planned" ? "○" : "●"}</div><div><h3>{text(event.label)}</h3><span>{event.kind === "planned" ? "Planned / expected event" : "Recorded event"}</span>{Boolean(event.detail) && <p>{text(event.detail)}</p>}</div></article>)}</div>
    </Section>

    <Section id="readiness" title="Records & Completion Readiness" subtitle={text(readiness.headline)}><ReadinessRows readiness={readiness} /></Section>

    <Section id="compliance" title="MPLADS Compliance" subtitle="Only deterministic rules establish compliance status">
      <div className="compliance-counts">{["PASS", "REVIEW", "NON_COMPLIANT", "NOT_APPLICABLE", "INSUFFICIENT_DATA"].map((result) => <div key={result}><span>{result === "NON_COMPLIANT" ? "Non-Compliant" : result === "REVIEW" ? "Requires Review" : result.replaceAll("_", " ")}</span><strong>{number.format(Number(counts[result] ?? 0))}</strong></div>)}</div>
      {actionableRules.length ? <div className="compact-row-list">{actionableRules.map((rule) => <ComplianceRow rule={rule} key={String(rule.rule_id)} />)}</div> : <EmptyState label="No actionable compliance issue; ordinary checks remain available below." />}
      <details className="all-rules"><summary>View all other rule checks ({ordinaryRules.length})</summary><div className="compact-row-list">{ordinaryRules.map((rule) => <ComplianceRow rule={rule} key={String(rule.rule_id)} />)}</div></details>
      <p className="section-note">Requires Review is not Non-Compliant. The states remain distinct.</p>
    </Section>

    <Section id="duplicates" title="Duplicate Work Review" subtitle="Candidates require comparison and are never confirmed automatically">
      {asRows(duplicates.review_candidates).length ? asRows(duplicates.review_candidates).map((candidate) => { const paired = asRecord(candidate.paired_work); return <article className="duplicate-card" key={text(candidate.pair_id)}><div className="candidate-banner"><AlertTriangle size={17} /><strong>Duplicate Review Candidate — officer comparison required.</strong></div><div className="pair-grid"><div><span>Current work</span><h3>{text(p.work_description)}</h3><p>{text(p.village)}, {text(p.block)}</p></div><div><span>Candidate work</span><h3>{text(paired.work_description)}</h3><p>{text(paired.village)}, {text(paired.block)}</p><Link href={`/works/${text(paired.work_id)}`}>Open {text(paired.work_id)}</Link></div></div><TechnicalDetails><pre>{JSON.stringify(candidate, null, 2)}</pre></TechnicalDetails></article>; }) : <div className="normal-callout"><CheckCircle2 size={17} /><strong>Normal — no corroborated duplicate candidate is currently flagged.</strong></div>}
    </Section>

    <Section id="peer" title="Comparison With Similar Works" subtitle={asRows(presentation.peer_comparisons).length ? `This work differs meaningfully from ${number.format(Number(asRows(presentation.peer_comparisons)[0].peer_group_size ?? 0))} comparable ${text(p.lifecycle_stage).replaceAll("_", " ").toLowerCase()}-stage works.` : "No significant peer difference is currently flagged."}>
      {asRows(presentation.peer_comparisons).length ? <div className="table-wrap"><table className="peer-table"><thead><tr><th>Metric</th><th>This work</th><th>Typical similar work</th><th>Comparison</th></tr></thead><tbody>{asRows(presentation.peer_comparisons).map((row) => { const metric = text(row.metric); return <tr key={metric}><td>{text(row.label, metricLabel(metric))}</td><td>{formatMetric(metric, row.observed_value)}</td><td>{formatMetric(metric, row.peer_median)}</td><td><StatePill state="analytical" label={text(row.comparison)} /></td></tr>; })}</tbody></table></div> : <div className="normal-callout"><CheckCircle2 size={17} /><strong>Normal / analytical context — no peer outlier is flagged.</strong></div>}
      <p className="analytical-disclaimer">Peer comparison supports prioritization. It does not establish a violation or wrongdoing.</p>
      <TechnicalDetails><p>Same-stage percentile: {text(d.anomaly.within_stage_anomaly_percentile_0_100)}</p><pre>{JSON.stringify(peer, null, 2)}</pre></TechnicalDetails>
    </Section>

    <Section id="forecast" title="Forecast / Predictive Signal" subtitle="Shown only as limited secondary context">
      <div className="forecast-columns"><div><h3>Observed now</h3>{scores.already_overdue_as_of === true && <article className="observed-card"><StatePill state="strong_issue" label="Observed overdue" /><p>{number.format(Number(p.overdue_days_as_of ?? 0))} days past expected completion.</p></article>}{scores.already_over_sanction_as_of !== true && scores.already_overdue_as_of !== true && <EmptyState label="No governed observed overdue or over-sanction condition is present." />}</div><div><h3>Predictive / early warning</h3><article className="prediction-card"><StatePill state="insufficient" label="Delay prediction unavailable" /><p>The available outcomes do not support a defensible delay classifier.</p></article>{scores.cost_overrun_serving_percentile_0_100 != null && <article className="prediction-card"><StatePill state="analytical" label="Cost-overrun early warning" /><p>Relative model signal: {number.format(Number(scores.cost_overrun_serving_percentile_0_100))}th percentile.</p><strong>Model reliability: Limited</strong></article>}</div></div>
      <TechnicalDetails><pre>{JSON.stringify(prediction, null, 2)}</pre></TechnicalDetails>
      {trend.has_supported_deviation === true && <details className="secondary-context"><summary>Recent Reporting Context</summary><div className="row-detail"><dl className="data-list"><Field label="Recent reporting activity" value={trend.assessment} /><Field label="Comparison period" value={trend.current_month} /><Field label="Scope" value={trend.group} /></dl><p>This is surrounding operational context only and does not by itself establish an issue with this work.</p><TechnicalDetails><pre>{JSON.stringify(trend.technical, null, 2)}</pre></TechnicalDetails></div></details>}
    </Section>

    <Section id="brief" title="AI-Assisted Case Explanation" subtitle="Explain the work, what happened, and the main issues">
      <div className="mode-line"><StatePill state={mode === "GROQ_GROUNDED" ? "analytical" : "context"} label={badge} /><span>All facts come from validated structured evidence. Groq is optional and explicit-click only.</span></div>
      <Explanation assessment={assessment} narrative={narrative} generated={mode === "GROQ_GROUNDED"} />
      <ReviewNote />
      <div className="brief-actions"><button className="button" onClick={() => explain.mutate()} disabled={explain.isPending}><Bot size={15} />{explain.isPending ? "Preparing grounded explanation…" : "Generate Grounded AI Explanation"}</button><a className="button secondary" href={api.caseReportUrl(workId)}><Download size={15} />Download Case Review Report</a></div>
      {explain.error && <p role="alert" className="inline-error">{explain.error.message}</p>}
      {explanation && <div className="provider-result"><CheckCircle2 size={15} /><span>{badge} · {provider}</span>{(provider.includes("429") || provider.includes("RATE")) && <p>Groq is temporarily rate-limited. The verified local explanation remains available.</p>}</div>}
      <TechnicalDetails><p>Mode <code>{mode}</code> · provider <code>{provider}</code></p><p>Normal navigation and PDF generation never contact Groq.</p></TechnicalDetails>
    </Section>

    <Section id="review" title="Officer Review & Corrective Action" subtitle={`Current case status: ${d.current_review_status}`}>
      <form className="form-grid" onSubmit={submitReview}><label>Officer / desk label<input required minLength={2} maxLength={120} value={actor} onChange={(event) => setActor(event.target.value)} /></label><label>Case status<select value={status} onChange={(event) => setStatus(event.target.value)}>{["OPEN", "IN_REVIEW", "NEEDS_CLARIFICATION", "ESCALATED", "RESOLVED", "FALSE_POSITIVE"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="wide">Controlled follow-up action<select required value={action} onChange={(event) => setAction(event.target.value)}>{Object.entries(FOLLOW_UP_ACTION_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label className="wide">Officer note<textarea required minLength={2} maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} /></label><div className="wide"><button className="button" disabled={review.isPending}><FileCheck2 size={15} />{review.isPending ? "Recording…" : "Save append-only review"}</button>{review.isSuccess && <span className="success-inline" role="status">Review and audit event recorded.</span>}</div></form>
      <p className="section-note">The officer selects the action. The system does not escalate or decide automatically. Runtime history may reset after a Render Free restart.</p>
      <div className="history-block"><h3>Append-only audit history</h3>{d.reviews.length ? d.reviews.map((row, index) => <article className="record-card" key={String(row.review_id ?? index)}><div className="record-card-head"><strong>{text(row.status).replaceAll("_", " ")}</strong><span>{text(row.created_at)}</span></div><p><strong>Follow-up:</strong> {FOLLOW_UP_ACTION_LABELS[text(row.follow_up_action)] ?? text(row.follow_up_action, "Legacy review — no action recorded")}</p><p>{text(row.note)}</p><small>{text(row.actor_label)} · {text(row.actor_role)} · {text(row.scope_label, "Scope not recorded")}</small></article>) : <EmptyState label="No officer review has been recorded yet." />}</div>
    </Section>
  </>;
}
