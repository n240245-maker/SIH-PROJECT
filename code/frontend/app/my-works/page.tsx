"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number } from "@/lib/format";
import { useScope } from "@/lib/scope";

const TABS = [
  ["RECOMMENDED", "Recommended"], ["ONGOING", "Ongoing"],
  ["COMPLETED", "Completed"], ["ATTENTION", "Needs Attention"],
] as const;

export default function MyWorksPage() {
  const { scope } = useScope(); const [tab, setTab] = useState<(typeof TABS)[number][0]>("RECOMMENDED");
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["my-works", scope, tab, search],
    queryFn: () => api.myWorks(scope, { page_size: 100, category: tab === "ATTENTION" ? undefined : tab, search }),
    enabled: scope.role === "MP",
  });
  if (scope.role !== "MP") return <div className="state-box"><div><strong>MP Portal required</strong><p>Select MP in the role menu to view My Works.</p></div></div>;
  if (query.isLoading) return <LoadingState label="Loading your works…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const rows = tab === "ATTENTION" ? query.data.items.filter((item) => item.needs_attention) : query.data.items;
  return <>
    <div className="page-title"><div><p className="eyebrow">MP Portal</p><h1>My Works</h1><p>Track recommended, ongoing, and completed works in your constituency.</p></div><Link className="button" href="/recommend-work">Recommend Work <ArrowRight size={15} /></Link></div>
    <div className="tabs" role="tablist">{TABS.map(([value, label]) => <button role="tab" aria-selected={tab === value} className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)}>{label}</button>)}</div>
    <div className="toolbar"><label className="search-box"><Search size={15} /><input aria-label="Search my works" placeholder="Search ID, title or location" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
    {rows.length === 0 ? <EmptyState label={tab === "ATTENTION" ? "No works need attention." : "No works are available in this category."} /> : <div className="work-card-grid">{rows.map((row) => <article className="work-card" key={`${row.record_type}-${row.id}`}><div className="work-card-head"><span>{row.id}</span><span className={`status-badge status-${row.status.toLowerCase().replaceAll("_", "-")}`}>{row.status.replaceAll("_", " ")}</span></div><h2>{row.title}</h2><p>{row.location}</p><dl><div><dt>{row.record_type === "RUNTIME_RECOMMENDATION" && row.category === "RECOMMENDED" ? "Proposed Cost" : "Project Cost"}</dt><dd>{row.cost_inr != null ? inr.format(row.cost_inr) : "Not available"}</dd></div><div><dt>Progress</dt><dd>{row.progress_pct != null ? `${number.format(row.progress_pct)}%` : "Not started"}</dd></div></dl>{row.needs_attention && <span className="attention-tag"><AlertTriangle size={13} />Needs Attention</span>}<Link className="card-link" href={row.record_type === "RUNTIME_RECOMMENDATION" ? `/recommendations/${row.id}` : `/works/${row.id}`}>Open record <ArrowRight size={14} /></Link></article>)}</div>}
  </>;
}
