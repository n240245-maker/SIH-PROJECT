"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useScope } from "@/lib/scope";
import { number, text } from "@/lib/format";
import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";

const metrics = ["recommendation_work_count", "recommended_amount_inr", "sanction_work_count", "sanctioned_amount_inr", "released_payment_count", "released_payment_amount_inr", "progress_report_count"];

export default function TrendsPage() {
  const { scope } = useScope(); const [metric, setMetric] = useState("recommendation_work_count"); const [groupType, setGroupType] = useState("STATE");
  const trend = useQuery({ queryKey: ["trends", scope, metric, groupType], queryFn: () => api.trends(scope, { metric, group_type: groupType, limit: 1200 }) });
  const hotspots = useQuery({ queryKey: ["hotspots", scope], queryFn: () => api.hotspots(scope) });
  const series = useMemo(() => {
    const rows = trend.data?.items ?? []; const first = rows[0]?.group_value;
    return rows.filter((row) => row.group_value === first).map((row) => ({ month: String(row.month).slice(0,7), value: Number(row.current_value ?? 0), baseline: Number(row.median ?? 0) }));
  }, [trend.data]);
  return <><div className="page-title"><div><p className="eyebrow">Cross-project intelligence</p><h1>Trends & hotspots</h1><p>Observed event trends and transparent prevalence shares. Hotspots are contextual aggregates, not opaque scores.</p></div></div>
    <div className="toolbar"><select aria-label="Trend group" value={groupType} onChange={(e) => setGroupType(e.target.value)}><option>STATE</option><option>DISTRICT</option><option>SECTOR</option><option>STATE_SECTOR</option><option>DISTRICT_SECTOR</option></select>
      <select aria-label="Trend metric" value={metric} onChange={(e) => setMetric(e.target.value)}>{metrics.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></div>
    <Section title="Monthly operational trend" subtitle="First permitted group in the selected scope; baseline median shown for comparison">
      {trend.isLoading ? <LoadingState /> : trend.error ? <ErrorState error={trend.error} /> : !series.length ? <EmptyState label={scope.role === "MP" ? "No MP-level trend series is present in the frozen artifact." : undefined} /> :
      <div style={{ width:"100%",height:330 }}><ResponsiveContainer><LineChart data={series}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8ee" /><XAxis dataKey="month" tick={{fontSize:10}} /><YAxis tick={{fontSize:10}} /><Tooltip /><Line type="monotone" dataKey="value" stroke="#0c756f" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="baseline" stroke="#d97706" strokeDasharray="5 4" dot={false} /></LineChart></ResponsiveContainer></div>}
      <p style={{color:"#637282",fontSize:11}}>Returned {trend.data?.returned ?? 0} of {trend.data?.total ?? 0} scoped records. API responses are deliberately bounded.</p>
    </Section>
    <Section title="Detector hotspots" subtitle="Separate observed shares by authority group; no composite hotspot score">
      {hotspots.isLoading ? <LoadingState /> : hotspots.error ? <ErrorState error={hotspots.error} /> : !hotspots.data?.items.length ? <EmptyState /> : <div className="table-wrap"><table><thead><tr><th>Group</th><th>Works</th><th>Top-decile unusualness</th><th>Duplicate review</th><th>Payment evidence</th><th>Persistent fund gap</th><th>Observed overdue</th><th>Compliance review</th></tr></thead><tbody>
        {hotspots.data.items.map((row, index) => <tr key={`${row.group_type}-${row.group_value}-${index}`}><td><strong>{text(row.group_label ?? row.group_value)}</strong><br /><small>{text(row.group_type)}</small></td><td>{number.format(Number(row.work_count ?? 0))}</td><td>{number.format(Number(row.top_10pct_anomaly_share ?? 0) * 100)}%</td><td>{number.format(Number(row.duplicate_review_share ?? 0) * 100)}%</td><td>{number.format(Number(row.payment_evidence_share ?? 0) * 100)}%</td><td>{number.format(Number(row.persistent_fund_gap_share ?? 0) * 100)}%</td><td>{number.format(Number(row.observed_overdue_share ?? 0) * 100)}%</td><td>{number.format(Number(row.compliance_review_share ?? 0) * 100)}%</td></tr>)}
      </tbody></table></div>}
    </Section>
  </>;
}
