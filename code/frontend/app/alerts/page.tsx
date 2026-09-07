"use client";

import { useQuery } from "@tanstack/react-query";
import { BellRing, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { number, text } from "@/lib/format";
import { friendlyEvidence } from "@/lib/presentation";
import { useScope } from "@/lib/scope";

export default function AlertCenterPage() {
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["v2-alerts", scope], queryFn: () => api.alerts(scope) });
  if (query.isLoading) return <LoadingState label="Loading alerts…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const grouped = new Map<string, { count: number; works: Set<string>; message: string }>();
  query.data.items.forEach((row) => {
    const key = String(row.alert_type ?? "OTHER_REVIEW_SIGNAL");
    const current = grouped.get(key) ?? { count: 0, works: new Set<string>(), message: text(row.message, "Evidence requires officer review.") };
    current.count += 1; current.works.add(String(row.work_id)); grouped.set(key, current);
  });
  return <>
    <div className="page-title"><div><p className="eyebrow">Evidence Centre</p><h1>Alerts Requiring Attention</h1><p>Review recorded issues and supporting evidence within your selected authority scope.</p></div><div className="alert-total"><BellRing size={18} /><strong>{number.format(query.data.total)}</strong><span>alert records</span></div></div>
    <div className="alert-guidance"><ShieldAlert size={18} /><p>Open a work to verify the underlying record. Missing site evidence is shown as operational context and does not add Review Priority points.</p></div>
    <Section title="Alert Families" subtitle="Grouped by the type of recorded issue">{!grouped.size ? <EmptyState /> : <div className="alert-category-list">{[...grouped.entries()].map(([key, value]) => <article className="alert-row" key={key}><span className="state-pill state-review">Requires Review</span><span className="compact-row-main"><strong>{friendlyEvidence(key)}</strong><small>{value.message}</small></span><span className="alert-count"><strong>{number.format(value.works.size)}</strong><small>works</small></span></article>)}</div>}</Section>
    <Section title="Recent Evidence" subtitle="Recent items in the selected authority scope"><div className="table-wrap"><table><thead><tr><th>Work</th><th>Evidence</th><th>Explanation</th></tr></thead><tbody>{query.data.items.map((row, index) => <tr key={`${row.work_id}-${row.alert_type}-${index}`}><td><Link className="work-link" href={`/works/${row.work_id}`}>{text(row.work_id)}</Link></td><td>{friendlyEvidence(row.alert_type)}</td><td>{text(row.message)}</td></tr>)}</tbody></table></div></Section>
  </>;
}
