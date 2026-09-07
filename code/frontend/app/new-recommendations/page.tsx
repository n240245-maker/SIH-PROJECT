"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { useScope } from "@/lib/scope";

export default function NewRecommendationsPage() {
  const { scope } = useScope(); const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["district-recommendations", scope, search],
    queryFn: () => api.recommendations(scope, { page_size: 100, search }),
    enabled: scope.role === "DISTRICT",
  });
  if (scope.role !== "DISTRICT") return <div className="state-box"><div><strong>District Authority required</strong><p>Select a District role to view new recommendations.</p></div></div>;
  if (query.isLoading) return <LoadingState label="Loading district recommendations…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const rows = query.data.items.filter((row) => !["COMPLETED", "CLOSED"].includes(row.status));
  return <>
    <div className="page-title"><div><p className="eyebrow">District Authority</p><h1>New Recommendations</h1><p>Review recommendations submitted by MPs in the selected district.</p></div></div>
    <div className="toolbar"><label className="search-box"><Search size={15} /><input aria-label="Search recommendations" placeholder="Search ID, title or location" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
    {rows.length === 0 ? <EmptyState label="No new recommendations in this district." /> : <div className="table-wrap"><table><thead><tr><th>Recommendation</th><th>Work</th><th>MP</th><th>Location</th><th>Proposed Cost</th><th>Pre-Check</th><th>Status</th><th></th></tr></thead><tbody>{rows.map((row) => <tr key={row.recommendation_id}><td><strong>{row.recommendation_id}</strong><br /><small>{row.created_at.slice(0, 10)}</small></td><td>{row.title}</td><td>{row.mp_name}</td><td>{row.village}, {row.district}</td><td>{inr.format(row.proposed_project_cost_inr)}</td><td>{String(row.precheck?.overall_status ?? "Not run")}</td><td><span className={`status-badge status-${row.status.toLowerCase().replaceAll("_", "-")}`}>{row.status_label}</span></td><td><Link className="work-link" href={`/recommendations/${row.recommendation_id}`}>Open <ArrowRight size={13} /></Link></td></tr>)}</tbody></table></div>}
  </>;
}
