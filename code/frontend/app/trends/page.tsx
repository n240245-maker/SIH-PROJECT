"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { number, text } from "@/lib/format";
import { useScope } from "@/lib/scope";

export default function TrendsPage() {
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["v2-performance", scope], queryFn: () => api.overview(scope) });
  if (query.isLoading) return <LoadingState label="Loading scoped comparisons…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const data = query.data; const rows = data.comparison.items;
  return <><div className="page-title"><div><p className="eyebrow">Area Trends</p><h1>Performance Comparisons</h1><p>Compare delivery, utilization and follow-up needs across your selected authority scope.</p></div></div>
    <Section title={`${data.comparison.level} high-priority comparison`} subtitle="Top groups by number of HIGH/CRITICAL works"><div style={{ width: "100%", height: 340 }}><ResponsiveContainer><BarChart data={rows.slice(0, 18)}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8ee" /><XAxis dataKey="label" tick={{ fontSize: 9 }} interval={0} angle={-25} textAnchor="end" height={80} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="high_priority_count" fill="#0c756f" name="High-priority works" /></BarChart></ResponsiveContainer></div></Section>
    <Section title={`${data.comparison.level} performance table`} subtitle="Utilization, completion, delay, high-priority and compliance shares are kept separate">{!rows.length ? <EmptyState /> : <div className="table-wrap"><table><thead><tr><th>{data.comparison.level}</th><th>Works</th><th>Utilization</th><th>Completion rate</th><th>Delay rate</th><th>High-priority rate</th><th>Compliance issue rate</th></tr></thead><tbody>{rows.map((row) => <tr key={String(row.label)}><td><strong>{text(row.label)}</strong></td><td>{number.format(Number(row.work_count ?? 0))}</td><td>{number.format(Number(row.utilization_pct ?? 0))}%</td><td>{number.format(Number(row.completion_rate_pct ?? 0))}%</td><td>{number.format(Number(row.delayed_rate_pct ?? 0))}%</td><td>{number.format(Number(row.high_priority_rate_pct ?? 0))}%</td><td>{number.format(Number(row.compliance_issue_rate_pct ?? 0))}%</td></tr>)}</tbody></table></div>}</Section>
    <p className="section-note">Area comparisons provide management context and do not change an individual work&apos;s Review Priority.</p>
  </>;
}
