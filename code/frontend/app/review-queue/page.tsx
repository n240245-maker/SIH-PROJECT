"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useScope } from "@/lib/scope";
import { inr, number } from "@/lib/format";
import { attentionLabel } from "@/lib/presentation";
import { Band, EmptyState, ErrorState, LoadingState } from "@/components/ui";

const evidenceTypes = [
  ["", "All evidence types"], ["OBSERVED_OVER_SANCTION", "Amount above sanction"],
  ["OBSERVED_OVERDUE", "Observed overdue"], ["PAYMENT_IRREGULARITY", "Payment chronology"],
  ["FUND_PROGRESS_REVIEW", "Payments & progress"], ["COMPLIANCE_REVIEW", "Compliance review"],
  ["DETERMINISTIC_NON_COMPLIANCE", "Deterministic non-compliance"],
  ["DUPLICATE_REVIEW_CANDIDATE", "Duplicate review candidate"], ["PEER_DEVIATION", "Peer comparison"],
] as const;

export default function ReviewQueuePage() {
  const { scope } = useScope();
  const [page, setPage] = useState(1); const [search, setSearch] = useState(""); const [debounced, setDebounced] = useState("");
  const [attention, setAttention] = useState(""); const [reviewNeed, setReviewNeed] = useState("ALL");
  const [band, setBand] = useState(""); const [lifecycle, setLifecycle] = useState("");
  const [sector, setSector] = useState(""); const [subSector, setSubSector] = useState("");
  const [alertType, setAlertType] = useState(""); const [duplicate, setDuplicate] = useState("");
  const [compliance, setCompliance] = useState(""); const [overdue, setOverdue] = useState("");
  const [overSanction, setOverSanction] = useState(""); const [reviewStatus, setReviewStatus] = useState("");
  useEffect(() => {
    const requestedAlert = new URLSearchParams(window.location.search).get("alert_type");
    if (!requestedAlert) return;
    const timer = window.setTimeout(() => setAlertType(requestedAlert), 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => { setDebounced(search); setPage(1); }, 300); return () => window.clearTimeout(timer); }, [search]);
  const filters = { page, page_size: 25, search: debounced, attention_level: attention, review_need: reviewNeed,
    band, lifecycle, sector, sub_sector: subSector, alert_type: alertType, duplicate: duplicate || undefined,
    compliance: compliance || undefined, overdue: overdue || undefined, over_sanction: overSanction || undefined,
    review_status: reviewStatus };
  const query = useQuery({ queryKey: ["queue", scope, filters], queryFn: () => api.queue(scope, filters) });
  const reset = () => { setAttention(""); setReviewNeed("ALL"); setBand(""); setLifecycle(""); setSector(""); setSubSector(""); setAlertType(""); setDuplicate(""); setCompliance(""); setOverdue(""); setOverSanction(""); setReviewStatus(""); setPage(1); };
  const exportPage = () => {
    if (!query.data?.items.length) return;
    const columns = ["work_id", "state_name", "district", "sector", "lifecycle_stage", "attention_level_label", "requires_review", "review_priority_score_0_100", "review_priority_band", "current_review_status"] as const;
    const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [columns.join(","), ...query.data.items.map((item) => columns.map((key) => escape(item[key])).join(","))].join("\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = `review-queue-page-${page}.csv`; link.click(); URL.revokeObjectURL(link.href);
  };
  return <><div className="page-title"><div><p className="eyebrow">Human review workflow</p><h1>Review queue</h1><p>Browse all works by officer-facing attention level, actionable review need, and frozen evidence.</p></div>
    <button className="button secondary" onClick={exportPage} disabled={!query.data?.items.length}><Download size={15} />Export current page</button></div>
    <div className="filter-panel">
      <div className="filter-group"><strong>Attention level</strong><select aria-label="Attention level" value={attention} onChange={(e) => { setAttention(e.target.value); setPage(1); }}><option value="">All attention levels</option>{["NORMAL", "LOW_ATTENTION", "MEDIUM_ATTENTION", "HIGH_ATTENTION", "IMMEDIATE_PRIORITY"].map((value) => <option value={value} key={value}>{attentionLabel(value)}</option>)}</select></div>
      <div className="filter-group"><strong>Review need</strong><select aria-label="Review need" value={reviewNeed} onChange={(e) => { setReviewNeed(e.target.value); setPage(1); }}><option value="ALL">All</option><option value="REQUIRES_REVIEW">Requires Review</option><option value="IMMEDIATE_PRIORITY">Immediate Priority</option></select></div>
      <div className="filter-group"><strong>Evidence type</strong><select aria-label="Evidence type" value={alertType} onChange={(e) => { setAlertType(e.target.value); setPage(1); }}>{evidenceTypes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div>
      <button className="button secondary" onClick={reset}>Clear filters</button>
    </div>
    <div className="toolbar wrap"><div style={{ position: "relative" }}><Search size={15} style={{ position: "absolute", left: 10, top: 11, color: "#637282" }} /><input aria-label="Search review queue" style={{ paddingLeft: 32 }} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search work, MP, district, sector…" /></div>
      <select aria-label="Priority band" value={band} onChange={(e) => { setBand(e.target.value); setPage(1); }}><option value="">All frozen bands</option>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((v) => <option key={v}>{v}</option>)}</select>
      <select aria-label="Lifecycle stage" value={lifecycle} onChange={(e) => { setLifecycle(e.target.value); setPage(1); }}><option value="">All lifecycle stages</option>{["PRE_SANCTION", "EXECUTION", "COMPLETION"].map((v) => <option key={v}>{v}</option>)}</select>
      <input aria-label="Sector" value={sector} onChange={(e) => setSector(e.target.value)} placeholder="Sector" /><input aria-label="Sub-sector" value={subSector} onChange={(e) => setSubSector(e.target.value)} placeholder="Sub-sector" />
      <select aria-label="Duplicate candidate" value={duplicate} onChange={(e) => setDuplicate(e.target.value)}><option value="">Any duplicate status</option><option value="true">Duplicate candidate</option><option value="false">No candidate</option></select>
      <select aria-label="Compliance" value={compliance} onChange={(e) => setCompliance(e.target.value)}><option value="">Any compliance status</option><option value="true">Compliance review</option><option value="false">No compliance review</option></select>
      <select aria-label="Observed overdue" value={overdue} onChange={(e) => setOverdue(e.target.value)}><option value="">Any schedule state</option><option value="true">Observed overdue</option><option value="false">Not observed overdue</option></select>
      <select aria-label="Observed over sanction" value={overSanction} onChange={(e) => setOverSanction(e.target.value)}><option value="">Any sanction state</option><option value="true">Observed over sanction</option><option value="false">Within visible sanction</option></select>
      <select aria-label="Officer review status" value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value)}><option value="">Any officer status</option>{["OPEN", "IN_REVIEW", "NEEDS_CLARIFICATION", "ESCALATED", "RESOLVED", "FALSE_POSITIVE"].map((v) => <option key={v}>{v.replaceAll("_", " ")}</option>)}</select>
    </div>
    <p className="section-note">State and district are controlled by the authority scope selector. Attention Level is a presentation aid derived from the frozen Review Priority and current actionable evidence. It does not change the underlying analytical score.</p>
    {query.isLoading ? <LoadingState label="Loading review queue…" /> : query.error ? <ErrorState error={query.error} /> : !query.data?.items.length ? <EmptyState /> : <>
      <div className="table-wrap"><table><thead><tr><th>Rank / work</th><th>Location & sector</th><th>Lifecycle</th><th>Attention</th><th>Governed Review Priority</th><th>Main reasons</th><th>Officer status</th><th>Sanctioned</th></tr></thead><tbody>
        {query.data.items.map((item) => <tr key={item.work_id}><td><small>#{item.review_priority_rank_overall}</small><br /><Link className="work-link" href={`/works/${item.work_id}`}>{item.work_id}</Link></td>
          <td>{item.district}<br /><small>{item.state_name} · {item.sector} / {item.sub_sector}</small></td><td>{item.lifecycle_stage}<br /><small>{item.source_current_status}</small></td>
          <td><span className={`attention-badge attention-${item.attention_level.toLowerCase()}`}>{item.attention_level_label}</span>{item.requires_review && <small className="requires-review">Requires Review</small>}</td>
          <td><strong>{number.format(item.review_priority_score_0_100)}</strong><br /><Band value={item.review_priority_band} /></td><td><ul className="compact-list">{item.attention_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></td><td>{item.current_review_status}</td><td>{item.sanctioned_amount_inr == null ? "—" : inr.format(item.sanctioned_amount_inr)}</td></tr>)}
      </tbody></table></div><div className="toolbar" style={{ justifyContent: "space-between", marginTop: 13 }}><span>Page {query.data.page} of {query.data.total_pages} · {number.format(query.data.total)} works</span><div><button className="button secondary" disabled={page <= 1} onClick={() => setPage((v) => v - 1)}>Previous</button> <button className="button secondary" disabled={page >= query.data.total_pages} onClick={() => setPage((v) => v + 1)}>Next</button></div></div></>}
  </>;
}
