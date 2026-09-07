"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, MapPinned } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number, text } from "@/lib/format";
import { useScope } from "@/lib/scope";
import type { Overview, Recommendation } from "@/lib/types";

type Row = Record<string, unknown>;

const ROLE_LABELS = { MOSPI: "MoSPI", STATE: "State Authority", DISTRICT: "District Authority", IA: "Implementing Agency", MP: "MP Portal" };

function idFor(title: string) { return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); }
function money(value: unknown) { const numeric = Number(value); return Number.isFinite(numeric) ? inr.format(numeric) : "Not available"; }
function metric(value: unknown, suffix = "") { const numeric = Number(value); return Number.isFinite(numeric) ? `${number.format(numeric)}${suffix}` : "Not available"; }

function Snapshot({ data, recommendationCount = 0, newRecommendationCount = 0, underReviewCount = 0 }: { data: Overview; recommendationCount?: number; newRecommendationCount?: number; underReviewCount?: number }) {
  const values = data.overview;
  const districtsNeedingAttention = data.comparison.items.filter((item) => Number(item.high_priority_count ?? 0) > 0).length;
  const cards: [string, unknown][] = data.role === "MP" ? [
    ["My Recommended Works", Number(values.recommended ?? 0) + recommendationCount],
    ["Ongoing Works", values.ongoing], ["Completed Works", values.completed], ["Works Needing Attention", values.works_requiring_review],
  ] : data.role === "DISTRICT" ? [
    ["New Recommendations", newRecommendationCount], ["Under Review", underReviewCount], ["Ongoing Works", values.ongoing],
    ["Works Needing Attention", values.works_requiring_review], ["Compliance Issues", values.pending_compliance_issues], ["Overdue Works", values.delayed],
  ] : data.role === "STATE" ? [
    ["Total Works", values.total_projects], ["High Priority", values.high_priority_review],
    ["Districts Needing Attention", districtsNeedingAttention], ["Overdue", values.delayed], ["Compliance Issues", values.pending_compliance_issues],
  ] : [
    ["Total Works", values.total_projects], ["Review Queue", values.high_priority_review], ["Overdue", values.delayed],
    ["Over Budget", values.over_budget], ["Similar Work Candidates", values.duplicate_candidates], ["Compliance Issues", values.pending_compliance_issues],
  ];
  return <div className="dashboard-kpis">{cards.map(([label, value]) => <article className="dashboard-kpi" key={String(label)}><span>{label}</span><strong>{metric(value)}</strong><small>Selected authority scope</small></article>)}</div>;
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

function RecommendationTable({ rows }: { rows: Recommendation[] }) {
  if (!rows.length) return <EmptyState label="No recommendations yet." />;
  return <div className="table-wrap"><table><thead><tr><th>ID</th><th>Work</th><th>Location</th><th>Proposed Cost</th><th>Status</th><th></th></tr></thead><tbody>{rows.slice(0, 8).map((row) => <tr key={row.recommendation_id}><td><strong>{row.recommendation_id}</strong></td><td>{row.title}</td><td>{row.village}, {row.district}</td><td>{money(row.proposed_project_cost_inr)}</td><td>{row.status_label}</td><td><Link className="work-link" href={`/recommendations/${row.recommendation_id}`}>Open</Link></td></tr>)}</tbody></table></div>;
}

function DashboardSection({ title, data, recommendations }: { title: string; data: Overview; recommendations: Recommendation[] }) {
  const lower = title.toLowerCase();
  const recommendedCount = recommendations.filter((item) => !["SANCTIONED", "IN_PROGRESS", "COMPLETED", "CLOSED"].includes(item.status)).length;
  const newRecommendationCount = recommendations.filter((item) => item.status === "RECOMMENDED").length;
  const underReviewCount = recommendations.filter((item) => ["UNDER_REVIEW", "NEEDS_CLARIFICATION", "ACCEPTED_FOR_PROCESSING"].includes(item.status)).length;
  if (lower.includes("recommendation") || lower.includes("recent activity") || lower.includes("recent updates")) return <RecommendationTable rows={recommendations} />;
  if (lower.startsWith("recommended")) return <ol className="recommended-actions">{data.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ol>;
  if (lower.includes("fund") || lower.includes("payment readiness")) return <FundFlow flow={data.fund_flow} />;
  if (lower.includes("map")) return <><div className="map-fallback"><MapPinned size={24} /><div><strong>Accessible monitoring heat table</strong><p>{data.map.license_note}</p></div></div><ComparisonTable data={data} /></>;
  if (lower.includes("sector")) return <SectorTable rows={data.sector_distribution} />;
  if (lower.includes("status") || lower.includes("health") || lower.includes("progress & milestones") || lower.includes("agency performance")) return <StatusGrid values={data.project_status} />;
  if (lower.includes("comparison") || lower.includes("performance") || lower.includes("block &") || lower.includes("fund flow monitoring")) return <ComparisonTable data={data} />;
  if (lower.includes("attention") || lower.includes("intervention") || lower.includes("action") || lower.includes("queue") || lower.includes("due") || lower.includes("issue") || lower.includes("submission") || lower.includes("compliance") || lower.includes("field verification")) return <AttentionTable rows={data.projects_requiring_attention} />;
  if (lower.includes("workflow")) return <ol className="decision-flow">{data.decision_workflow.map((step) => <li key={step}>{step.replaceAll("_", " ")}</li>)}</ol>;
  if (lower.includes("trend")) return <ComparisonTable data={data} />;
  if (lower.includes("overview") || lower.includes("summary") || lower === "my works") return <Snapshot data={data} recommendationCount={recommendedCount} newRecommendationCount={newRecommendationCount} underReviewCount={underReviewCount} />;
  return <Snapshot data={data} recommendationCount={recommendedCount} newRecommendationCount={newRecommendationCount} underReviewCount={underReviewCount} />;
}

export default function OverviewPage() {
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["v2-overview", scope], queryFn: () => api.overview(scope) });
  const recommendations = useQuery({ queryKey: ["dashboard-recommendations", scope], queryFn: () => api.recommendations(scope, { page_size: 100 }), enabled: ["MP", "DISTRICT"].includes(scope.role) });
  if (query.isLoading) return <LoadingState label="Loading your dashboard…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const data = query.data;
  const records = recommendations.data?.items ?? [];
  const title = { MOSPI: "MPLADS Overview", STATE: "State Overview", DISTRICT: "District Operations", IA: "Agency Operations", MP: "My MPLADS Works" }[data.role];
  const action = data.role === "MP" ? { href: "/recommend-work", label: "Recommend Work" } : data.role === "DISTRICT" ? { href: "/new-recommendations", label: "New Recommendations" } : { href: "/review-queue", label: "Open Review Queue" };
  return <>
    <div className="page-title dashboard-title"><div><p className="eyebrow">{ROLE_LABELS[data.role]}</p><h1>{title}</h1><p>{data.primary_question}</p></div><Link className="button" href={action.href}>{action.label} <ArrowRight size={15} /></Link></div>
    <nav className="dashboard-nav" aria-label="Dashboard sections">{data.section_order.map((title) => <a key={title} href={`#${idFor(title)}`}>{title}</a>)}</nav>
    {data.section_order.map((section) => <Section key={section} id={idFor(section)} title={section}><DashboardSection title={section} data={data} recommendations={records} /></Section>)}
  </>;
}
