"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Band, EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number } from "@/lib/format";
import { useScope } from "@/lib/scope";

function bool(value: unknown) { return value === true || String(value).toLowerCase() === "true"; }

export default function ReviewQueuePage() {
  const { scope } = useScope();
  const [page, setPage] = useState(1); const [search, setSearch] = useState(""); const [debounced, setDebounced] = useState("");
  const [reviewNeed, setReviewNeed] = useState("ALL"); const [band, setBand] = useState("");
  const [lifecycle, setLifecycle] = useState(""); const [sector, setSector] = useState(""); const [subSector, setSubSector] = useState("");
  useEffect(() => { const timer = window.setTimeout(() => { setDebounced(search); setPage(1); }, 250); return () => window.clearTimeout(timer); }, [search]);
  const filters = { page, page_size: 25, search: debounced, review_need: reviewNeed, band, lifecycle, sector, sub_sector: subSector };
  const query = useQuery({ queryKey: ["v2-review-queue", scope, filters], queryFn: () => api.queue(scope, filters) });
  const reset = () => { setSearch(""); setReviewNeed("ALL"); setBand(""); setLifecycle(""); setSector(""); setSubSector(""); setPage(1); };
  const exportPage = () => {
    if (!query.data?.items.length) return;
    const columns = ["work_id", "state_name", "district", "sector", "lifecycle_stage", "attention_level", "requires_review", "review_priority_score_0_100", "review_priority_band", "monthly_evidence_status"] as const;
    const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [columns.join(","), ...query.data.items.map((item) => columns.map((key) => escape(item[key])).join(","))].join("\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = `trace-x-kavach-review-queue-${page}.csv`; link.click(); URL.revokeObjectURL(link.href);
  };
  return <>
    <div className="page-title"><div><p className="eyebrow">Officer Review</p><h1>Review Queue</h1><p>Works are ordered by Review Priority to help authorized officers plan verification.</p></div><button className="button secondary" onClick={exportPage} disabled={!query.data?.items.length}><Download size={15} />Export Current Page</button></div>
    <div className="filter-panel queue-filters">
      <label className="filter-group"><strong>Review need</strong><select aria-label="Review need" value={reviewNeed} onChange={(event) => { setReviewNeed(event.target.value); setPage(1); }}><option value="ALL">All works</option><option value="REQUIRES_REVIEW">Requires Review</option></select></label>
      <label className="filter-group"><strong>Priority band</strong><select aria-label="Priority band" value={band} onChange={(event) => { setBand(event.target.value); setPage(1); }}><option value="">All bands</option>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label className="filter-group"><strong>Lifecycle</strong><select aria-label="Lifecycle" value={lifecycle} onChange={(event) => { setLifecycle(event.target.value); setPage(1); }}><option value="">All stages</option>{["PRE_SANCTION", "EXECUTION", "COMPLETION"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <button className="button secondary" onClick={reset}>Clear filters</button>
    </div>
    <div className="toolbar wrap"><div className="search-box"><Search size={15} /><input aria-label="Search review queue" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search work or description…" /></div><input aria-label="Sector" value={sector} onChange={(event) => { setSector(event.target.value); setPage(1); }} placeholder="Sector" /><input aria-label="Sub-sector" value={subSector} onChange={(event) => { setSubSector(event.target.value); setPage(1); }} placeholder="Sub-sector" /></div>
    <p className="section-note">Authority scope is enforced again by FastAPI. Missing site evidence is shown for operations but contributes zero points to Review Priority.</p>
    {query.isLoading ? <LoadingState label="Loading the scoped review queue…" /> : query.error ? <ErrorState error={query.error} /> : !query.data?.items.length ? <EmptyState /> : <>
      <div className="table-wrap"><table><thead><tr><th>Work</th><th>Location & sector</th><th>Lifecycle</th><th>Attention</th><th>Review Priority</th><th>Observed evidence</th><th>Sanctioned</th></tr></thead><tbody>{query.data.items.map((item) => {
        const evidence = [bool(item.observed_delay) && "Observed delay", bool(item.observed_cost_overrun) && "Observed cost overrun", bool(item.has_duplicate_candidate) && "Duplicate candidate", item.monthly_evidence_status === "OVERDUE" && "Site evidence overdue"].filter(Boolean);
        return <tr key={item.work_id}><td><Link className="work-link" href={`/works/${item.work_id}`}>{item.work_id}</Link><br /><small>{item.current_status}</small></td><td>{item.district}<br /><small>{item.state_name} · {item.sector} / {item.sub_sector}</small></td><td>{item.lifecycle_stage}</td><td><span className="attention-badge">{item.attention_level}</span>{bool(item.requires_review) && <small className="requires-review">Requires Review</small>}</td><td><strong>{number.format(item.review_priority_score_0_100)}</strong><br /><Band value={item.review_priority_band} /></td><td>{evidence.length ? <ul className="compact-list">{evidence.map((reason) => <li key={String(reason)}>{reason}</li>)}</ul> : "Routine monitoring"}</td><td>{item.sanctioned_amount_inr == null ? "—" : inr.format(item.sanctioned_amount_inr)}</td></tr>;
      })}</tbody></table></div>
      <div className="toolbar pagination"><span>Page {query.data.page} of {query.data.total_pages} · {number.format(query.data.total)} works</span><div><button className="button secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button> <button className="button secondary" disabled={page >= query.data.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></div>
    </>}
  </>;
}
