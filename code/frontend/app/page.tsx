"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useScope } from "@/lib/scope";
import { inr, number } from "@/lib/format";
import { Band, EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { attentionLabel, familyLabel } from "@/lib/presentation";

const colors = ["#7a1f1b", "#d97706", "#0c756f", "#7890a3"];

export default function OverviewPage() {
  const { scope } = useScope();
  const overview = useQuery({ queryKey: ["overview", scope], queryFn: () => api.overview(scope) });
  const queue = useQuery({ queryKey: ["queue-preview", scope], queryFn: () => api.queue(scope, { page: 1, page_size: 5 }) });
  if (overview.isLoading) return <LoadingState />;
  if (overview.error || !overview.data) return <ErrorState error={overview.error} />;
  const data = overview.data;
  const bands = Object.entries(data.priority_bands).map(([name, value]) => ({ name, value }));
  const attentionOrder = ["NORMAL", "LOW_ATTENTION", "MEDIUM_ATTENTION", "HIGH_ATTENTION", "IMMEDIATE_PRIORITY"];
  const attention = attentionOrder.map((name) => ({ name, value: data.attention_levels[name] ?? 0, pct: data.attention_level_percentages[name] ?? 0 }));
  return <>
    <div className="page-title"><div><p className="eyebrow">Operational overview</p><h1>Programme monitoring snapshot</h1><p>Scope-aware oversight of sanctions, execution, review signals, and observed conditions.</p></div>
      <Link className="button" href="/review-queue">Open review queue <ArrowRight size={15} /></Link></div>
    <div className="notice">{data.language_note} Multiple signals for a work are fused under the governed policy and never counted as separate verdicts.</div>
    <div className="kpi-grid">
      <div className="kpi"><span>Works in scope</span><strong>{number.format(data.work_count)}</strong><small>All lifecycle stages</small></div>
      <div className="kpi"><span>Requires Review</span><strong>{number.format(data.requires_review_count)}</strong><small>Current actionable evidence</small></div>
      <div className="kpi"><span>Mean Review Priority</span><strong>{number.format(data.mean_review_priority ?? 0)}</strong><small>Deterministic 0–100 triage score</small></div>
      <div className="kpi"><span>Immediate Priority</span><strong>{number.format(data.immediate_priority_count)}</strong><small>Frozen CRITICAL band</small></div>
    </div>
    <Section title="Attention Level Distribution" subtitle="Natural population derived from the frozen snapshot — categories were not artificially balanced">
      <div className="attention-distribution" title="Distribution reflects the current frozen analytical snapshot. Categories were not artificially balanced.">{attention.map((item, index) => <div className="attention-row" key={item.name}><span className={`attention-dot attention-${item.name.toLowerCase()}`} /><strong>{attentionLabel(item.name)}</strong><div className="track"><div className="fill" style={{ width: `${item.pct}%`, background: colors[index % colors.length] }} /></div><span>{number.format(item.value)} works</span><b>{number.format(item.pct)}%</b></div>)}</div>
      <p className="section-note" title={data.attention_level_note}>{data.attention_level_note}</p>
    </Section>
    <div className="grid-2">
      <Section title="Priority distribution" subtitle="Count of works by human-review band">
        <div style={{ width: "100%", height: 230 }}><ResponsiveContainer><PieChart><Pie data={bands} dataKey="value" nameKey="name" innerRadius={55} outerRadius={88} paddingAngle={2}>
          {bands.map((item, index) => <Cell key={item.name} fill={colors[index % colors.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
        <div className="metric-bars">{bands.map((item, index) => <div className="metric-row" key={item.name}><Band value={item.name} /><div className="track"><div className="fill" style={{ width: `${data.work_count ? item.value / data.work_count * 100 : 0}%`, background: colors[index] }} /></div><strong>{item.value}</strong></div>)}</div>
      </Section>
      <Section title="Financial & execution snapshot" subtitle={`Frozen snapshot ${data.as_of_date ?? "not available"}`}>
        <dl className="data-list"><div><dt>Sanctioned amount</dt><dd>{inr.format(data.financial_snapshot.sanctioned_amount_inr)}</dd></div>
          <div><dt>Released payments</dt><dd>{inr.format(data.financial_snapshot.released_amount_inr)}</dd></div>
          <div><dt>Observed over-sanction</dt><dd>{number.format(data.financial_snapshot.observed_over_sanction_count)} works</dd></div>
          <div><dt>Payment evidence</dt><dd>{number.format(data.review_signals.payment_evidence_work_count)} works</dd></div>
          <div><dt>Duplicate review candidates</dt><dd>{number.format(data.review_signals.duplicate_review_work_count)} works</dd></div>
          <div><dt>Compliance review</dt><dd>{number.format(data.review_signals.compliance_review_work_count)} works</dd></div></dl>
      </Section>
    </div>
    <Section title="Highest-priority review items" subtitle="Top five in the selected authority scope">
      {queue.isLoading ? <LoadingState label="Loading queue preview…" /> : queue.error ? <ErrorState error={queue.error} /> : !queue.data?.items.length ? <EmptyState /> :
      <div className="table-wrap"><table><thead><tr><th>Work</th><th>Location</th><th>Stage</th><th>Review Priority</th><th>Primary contributor</th><th>Status</th></tr></thead><tbody>
        {queue.data.items.map((item) => <tr key={item.work_id}><td><Link className="work-link" href={`/works/${item.work_id}`}>{item.work_id}</Link><br /><small>{item.sector}</small></td><td>{item.district}<br /><small>{item.state_name}</small></td><td>{item.lifecycle_stage}</td><td><strong>{number.format(item.review_priority_score_0_100)}</strong> <Band value={item.review_priority_band} /><br /><small>{attentionLabel(item.attention_level)}</small></td><td>{familyLabel(item.top_contributor_1_family)}<br /><small>{item.attention_reasons?.[0] ?? item.top_contributor_1_summary}</small></td><td>{item.current_review_status}</td></tr>)}
      </tbody></table></div>}
    </Section>
  </>;
}
