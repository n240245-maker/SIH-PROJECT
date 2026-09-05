"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, CheckCircle2, MapPinned, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number, text } from "@/lib/format";
import { useScope } from "@/lib/scope";
import type { Overview } from "@/lib/types";

type Row = Record<string, unknown>;

const ROLE_LABELS = { MOSPI: "Ministry of Statistics and Programme Implementation", STATE: "State Nodal Authority", DISTRICT: "District Authority", IA: "Implementing Agency", MP: "Member of Parliament" };

function idFor(title: string) { return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); }
function money(value: unknown) { const numeric = Number(value); return Number.isFinite(numeric) ? inr.format(numeric) : "Not available"; }
function metric(value: unknown, suffix = "") { const numeric = Number(value); return Number.isFinite(numeric) ? `${number.format(numeric)}${suffix}` : "Not available"; }

function Snapshot({ data }: { data: Overview }) {
  const values = data.overview;
  const cards: [string, unknown][] = [
    ["Works in scope", values.total_projects], ["Completed", values.completed], ["Ongoing", values.ongoing],
    ["Observed delayed", values.delayed], ["High-priority review", values.high_priority_review],
    ["Works requiring review", values.works_requiring_review], ["Site evidence overdue", values.site_evidence_overdue],
    ["Pending compliance issues", values.pending_compliance_issues],
  ];
  return <div className="dashboard-kpis">{cards.map(([label, value]) => <article className="dashboard-kpi" key={String(label)}><span>{label}</span><strong>{metric(value)}</strong><small>Within the selected authority scope</small></article>)}</div>;
}

function FundFlow({ flow }: { flow: Row }) {
  const cards: [string, unknown][] = [
    ["Allocated", flow.allocated_amount_inr], ["Sanctioned", flow.sanctioned_amount_inr],
    ["Released", flow.released_amount_inr], ["Recorded utilization", flow.utilized_amount_inr],
    ["Unspent released balance", flow.unspent_released_amount_inr],
  ];
  return <><div className="fund-flow-strip">{cards.map(([label, value], index) => <article key={String(label)}><span>{label}</span><strong>{money(value)}</strong>{index < cards.length - 1 && <ArrowRight size={17} aria-hidden="true" />}</article>)}</div>
    <div className="comparison-note"><strong>Utilization of sanction:</strong> {metric(flow.utilization_pct_of_sanction, "%")}<span>Current-year source utilization {metric(flow.current_year_utilization_pct, "%")} · previous year {metric(flow.previous_year_utilization_pct, "%")}</span></div></>;
}

function StatusGrid({ values }: { values: Record<string, number> }) {
  const total = Math.max(1, Object.values(values).reduce((sum, value) => sum + value, 0));
  return <div className="status-bars">{Object.entries(values).map(([label, value]) => <div key={label}><div><strong>{label.replaceAll("_", " ")}</strong><span>{number.format(value)} works · {number.format(value / total * 100)}%</span></div><div className="track"><span style={{ width: `${value / total * 100}%` }} /></div></div>)}</div>;
}

function ComparisonTable({ data }: { data: Overview }) {
  const rows = data.comparison.items;
  if (!rows.length) return <EmptyState />;
  return <div className="table-wrap"><table><thead><tr><th>{data.comparison.level}</th><th>Works</th><th>Utilization</th><th>Completion</th><th>Observed delayed</th><th>High priority</th><th>Compliance follow-up</th></tr></thead><tbody>{rows.slice(0, 24).map((row) => <tr key={String(row.label)}><td><strong>{text(row.label)}</strong></td><td>{metric(row.work_count)}</td><td>{metric(row.utilization_pct, "%")}</td><td>{metric(row.completion_rate_pct, "%")}</td><td>{metric(row.delayed_count)}</td><td>{metric(row.high_priority_count)}</td><td>{metric(row.compliance_issue_count)}</td></tr>)}</tbody></table></div>;
}

function AttentionTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <EmptyState label="No projects require attention in this scope." />;
  return <div className="table-wrap"><table><thead><tr><th>Work</th><th>Project / location</th><th>Main issue</th><th>Review Priority</th><th>Officer status</th></tr></thead><tbody>{rows.map((row) => <tr key={String(row.work_id)}><td><Link className="work-link" href={`/works/${row.work_id}`}>{text(row.work_id)}</Link></td><td><strong>{text(row.project)}</strong><br /><small>{text(row.location)}</small></td><td>{text(row.main_issue)}</td><td>{metric(row.review_priority)} <span className={`band band-${String(row.review_priority_band).toLowerCase()}`}>{text(row.review_priority_band)}</span></td><td>{text(row.officer_case_status)}</td></tr>)}</tbody></table></div>;
}

function SectorTable({ rows }: { rows: Row[] }) {
  return <div className="sector-grid">{rows.slice(0, 8).map((row) => <article key={String(row.sector)}><strong>{text(row.sector)}</strong><span>{money(row.sanctioned_amount_inr)}</span><small>{metric(row.share_pct, "%")} of scoped sanction</small></article>)}</div>;
}

function DashboardSection({ title, data, generatedBrief }: { title: string; data: Overview; generatedBrief?: Row | null }) {
  const lower = title.toLowerCase();
  if (lower.includes("brief")) return <div className="morning-brief"><div><span>Deterministic morning brief</span>{data.morning_brief.facts.map((fact) => <p key={fact}><CheckCircle2 size={15} />{fact}</p>)}</div>{generatedBrief && <p className="generated-brief"><Bot size={16} />{text(generatedBrief.message, "Structured brief refreshed from current local evidence.")}</p>}</div>;
  if (lower.startsWith("recommended")) return <ol className="recommended-actions">{data.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ol>;
  if (lower.includes("fund") || lower.includes("payment readiness")) return <FundFlow flow={data.fund_flow} />;
  if (lower.includes("map")) return <><div className="map-fallback"><MapPinned size={24} /><div><strong>Accessible monitoring heat table</strong><p>{data.map.license_note}</p></div></div><ComparisonTable data={data} /></>;
  if (lower.includes("sector")) return <SectorTable rows={data.sector_distribution} />;
  if (lower.includes("status") || lower.includes("health") || lower.includes("progress & milestones") || lower.includes("agency performance")) return <StatusGrid values={data.project_status} />;
  if (lower.includes("comparison") || lower.includes("performance") || lower.includes("block &") || lower.includes("fund flow monitoring")) return <ComparisonTable data={data} />;
  if (lower.includes("attention") || lower.includes("intervention") || lower.includes("action") || lower.includes("queue") || lower.includes("due") || lower.includes("issue") || lower.includes("submission") || lower.includes("compliance") || lower.includes("field verification")) return <AttentionTable rows={data.projects_requiring_attention} />;
  if (lower.includes("workflow")) return <ol className="decision-flow">{data.decision_workflow.map((step) => <li key={step}>{step.replaceAll("_", " ")}</li>)}</ol>;
  if (lower.includes("insight")) return <div className="insight-list"><p>Comparisons are calculated only inside the selected authority scope.</p><p>High-priority overlap is displayed once per work; warning rows do not multiply urgency.</p><p>Geo-evidence availability is operational context and contributes zero Review Priority points.</p></div>;
  if (lower.includes("overview") || lower.includes("summary")) return <Snapshot data={data} />;
  return <Snapshot data={data} />;
}

export default function OverviewPage() {
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["v2-overview", scope], queryFn: () => api.overview(scope) });
  const brief = useMutation({ mutationFn: () => api.dashboardBrief(scope) });
  const [layer, setLayer] = useState("Fund Utilization");
  if (query.isLoading) return <LoadingState label="Loading the local synthetic-demo dashboard…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const data = query.data;
  return <>
    <div className="page-title dashboard-title"><div><p className="eyebrow">{ROLE_LABELS[data.role]} dashboard · synthetic demo-v2</p><h1>{data.primary_question}</h1><p>{data.synthetic_disclaimer}</p></div><Link className="button" href="/review-queue">Open review queue <ArrowRight size={15} /></Link></div>
    <div className="governance-banner"><ShieldCheck size={18} /><p>{data.language_note} All values on this branch use clearly labelled synthetic demonstration data.</p></div>
    <nav className="dashboard-nav" aria-label="Dashboard sections">{data.section_order.map((title) => <a key={title} href={`#${idFor(title)}`}>{title}</a>)}</nav>
    <div className="dashboard-controls"><label>Monitoring map layer<select value={layer} onChange={(event) => setLayer(event.target.value)}>{data.map.layer_options.map((item) => <option key={item}>{item}</option>)}</select></label><button className="button secondary" onClick={() => brief.mutate()} disabled={brief.isPending}><Bot size={15} />{brief.isPending ? "Preparing…" : "Generate structured brief"}</button><span>Selected view: {layer}</span></div>
    {data.section_order.map((title) => <Section key={title} id={idFor(title)} title={title} subtitle={title.toLowerCase().includes("brief") ? "Generated locally from structured evidence; no Groq call is made." : undefined}><DashboardSection title={title} data={data} generatedBrief={brief.data} /></Section>)}
  </>;
}
