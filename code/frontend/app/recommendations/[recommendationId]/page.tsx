"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, FileText, MapPin, Upload, UserRound } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { EmptyState, ErrorState, LoadingState, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, number, text } from "@/lib/format";
import { asRecord, asRows } from "@/lib/presentation";
import { useScope } from "@/lib/scope";

async function encoded(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  return window.btoa(binary);
}

function friendlyLabel(value: unknown) {
  return text(value).toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function activityTime(value: unknown) {
  const parsed = new Date(text(value));
  if (Number.isNaN(parsed.getTime())) return text(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
    timeZone: "Asia/Kolkata", timeZoneName: "short",
  }).format(parsed);
}

function ActionPanel({ id, status }: { id: string; status: string }) {
  const { scope } = useScope(); const queryClient = useQueryClient();
  const [message, setMessage] = useState(""); const [actor, setActor] = useState(scope.role === "MP" ? "MP Office" : "District Desk");
  const [sanction, setSanction] = useState({ sanctioned_cost_inr: "", sanction_date: "", implementing_agency: "", expected_start_date: "", expected_completion_date: "" });
  const [progress, setProgress] = useState({ actual_start_date: "", physical_progress_pct: "", financial_progress_pct: "", progress_note: "" });
  const [payment, setPayment] = useState({ payment_amount_inr: "", payment_release_date: "", payment_request_date: "", authorization_date: "" });
  const action = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.recommendationAction(id, scope, { ...payload, actor_label: actor }),
    onSuccess: async () => { setMessage(""); await queryClient.invalidateQueries({ queryKey: ["recommendation", id] }); },
  });
  const submit = (event: FormEvent, payload: Record<string, unknown>) => { event.preventDefault(); action.mutate(payload); };
  if (scope.role === "MP" && status === "NEEDS_CLARIFICATION") return <form className="action-form" onSubmit={(event) => submit(event, { action: "PROVIDE_CLARIFICATION", message })}><h3>Provide Clarification</h3><label>Your response<textarea required minLength={2} value={message} onChange={(event) => setMessage(event.target.value)} /></label><button className="button" disabled={action.isPending}>Send Clarification</button>{action.error && <p className="inline-error">{action.error.message}</p>}</form>;
  if (scope.role !== "DISTRICT") return <p className="section-note">The District Authority will record the next administrative action.</p>;
  return <div className="district-actions"><label>Officer / desk label<input value={actor} onChange={(event) => setActor(event.target.value)} /></label>
    {["RECOMMENDED", "UNDER_REVIEW"].includes(status) && <div className="action-split"><form className="action-form" onSubmit={(event) => submit(event, { action: "REQUEST_CLARIFICATION", message })}><h3>Request Clarification</h3><label>Message<textarea required minLength={2} value={message} onChange={(event) => setMessage(event.target.value)} /></label><button className="button secondary" disabled={action.isPending}>Request Clarification</button></form><div className="action-form"><h3>Accept for Processing</h3><p>Move this recommendation to administrative processing. This does not sanction the work.</p><button className="button" onClick={() => action.mutate({ action: "ACCEPT_FOR_PROCESSING" })} disabled={action.isPending}>Accept for Processing</button></div></div>}
    {status === "ACCEPTED_FOR_PROCESSING" && <form className="form-grid action-form" onSubmit={(event) => submit(event, { action: "ADD_SANCTION", ...sanction, sanctioned_cost_inr: Number(sanction.sanctioned_cost_inr) })}><h3 className="wide">Add Sanction Details</h3><label>Sanctioned Cost (₹)<input required min="1" type="number" value={sanction.sanctioned_cost_inr} onChange={(event) => setSanction({ ...sanction, sanctioned_cost_inr: event.target.value })} /></label><label>Sanction Date<input required type="date" value={sanction.sanction_date} onChange={(event) => setSanction({ ...sanction, sanction_date: event.target.value })} /></label><label className="wide">Implementing Agency<input required value={sanction.implementing_agency} onChange={(event) => setSanction({ ...sanction, implementing_agency: event.target.value })} /></label><label>Expected Start Date<input required type="date" value={sanction.expected_start_date} onChange={(event) => setSanction({ ...sanction, expected_start_date: event.target.value })} /></label><label>Expected Completion Date<input required type="date" value={sanction.expected_completion_date} onChange={(event) => setSanction({ ...sanction, expected_completion_date: event.target.value })} /></label><button className="button wide" disabled={action.isPending}>Save Sanction Details</button></form>}
    {["SANCTIONED", "IN_PROGRESS"].includes(status) && <div className="action-split"><form className="form-grid action-form" onSubmit={(event) => submit(event, { action: "UPDATE_PROGRESS", ...progress, physical_progress_pct: Number(progress.physical_progress_pct), financial_progress_pct: progress.financial_progress_pct ? Number(progress.financial_progress_pct) : null })}><h3 className="wide">Update Progress</h3><label>Actual Start Date<input type="date" value={progress.actual_start_date} onChange={(event) => setProgress({ ...progress, actual_start_date: event.target.value })} /></label><label>Physical Progress %<input required min="0" max="100" type="number" value={progress.physical_progress_pct} onChange={(event) => setProgress({ ...progress, physical_progress_pct: event.target.value })} /></label><label>Financial Progress %<input min="0" type="number" value={progress.financial_progress_pct} onChange={(event) => setProgress({ ...progress, financial_progress_pct: event.target.value })} /></label><label>Progress Note<input value={progress.progress_note} onChange={(event) => setProgress({ ...progress, progress_note: event.target.value })} /></label><button className="button wide" disabled={action.isPending}>Update Progress</button></form><form className="form-grid action-form" onSubmit={(event) => submit(event, { action: "ADD_PAYMENT", ...payment, payment_amount_inr: Number(payment.payment_amount_inr) })}><h3 className="wide">Add Payment</h3><label>Released Amount (₹)<input required min="1" type="number" value={payment.payment_amount_inr} onChange={(event) => setPayment({ ...payment, payment_amount_inr: event.target.value })} /></label><label>Release Date<input required type="date" value={payment.payment_release_date} onChange={(event) => setPayment({ ...payment, payment_release_date: event.target.value })} /></label><label>Request Date<input type="date" value={payment.payment_request_date} onChange={(event) => setPayment({ ...payment, payment_request_date: event.target.value })} /></label><label>Authorization Date<input type="date" value={payment.authorization_date} onChange={(event) => setPayment({ ...payment, authorization_date: event.target.value })} /></label><button className="button wide" disabled={action.isPending}>Add Payment</button></form></div>}
    {status === "IN_PROGRESS" && <button className="button secondary" onClick={() => action.mutate({ action: "MARK_COMPLETED" })} disabled={action.isPending}><Check size={15} />Mark Completed</button>}
    {action.error && <p className="inline-error" role="alert">{action.error.message}</p>}
  </div>;
}

function DocumentPanel({ id, documents }: { id: string; documents: Record<string, unknown>[] }) {
  const { scope } = useScope(); const queryClient = useQueryClient(); const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState("SUPPORTING_DOCUMENT");
  const upload = useMutation({ mutationFn: async () => {
    if (!file) throw new Error("Choose a file to upload.");
    return api.uploadRecommendationDocument(id, scope, scope.role === "MP" ? "MP Office" : "District Desk", { document_type: type, original_filename: file.name, media_type: file.type, content_base64: await encoded(file) });
  }, onSuccess: async () => { setFile(null); await queryClient.invalidateQueries({ queryKey: ["recommendation", id] }); } });
  return <><div className="document-list">{documents.length ? documents.map((item) => <article key={String(item.document_id)}><FileText size={18} /><div><strong>{friendlyLabel(item.document_type)}</strong><p>{text(item.original_filename)} · {number.format(Number(item.size_bytes) / 1024)} KB</p><small>{String(item.media_type).startsWith("image/") ? text(asRecord(item.location_check).result, "Photo location unavailable") : "Stored securely"}</small></div></article>) : <EmptyState label="No documents uploaded." />}</div>{["MP", "DISTRICT"].includes(scope.role) && <div className="upload-row"><select aria-label="Document type" value={type} onChange={(event) => setType(event.target.value)}>{["ESTIMATE", "SUPPORTING_DOCUMENT", "SITE_PHOTO", "SANCTION_ORDER", "PROGRESS_PHOTO", "COMPLETION_PHOTO", "UTILIZATION_CERTIFICATE", "HANDOVER_DOCUMENT"].map((item) => <option key={item} value={item}>{friendlyLabel(item)}</option>)}</select><input aria-label="Choose document" type="file" accept="application/pdf,image/jpeg,image/png" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><button className="button" disabled={!file || upload.isPending} onClick={() => upload.mutate()}><Upload size={15} />Upload</button></div>}{upload.error && <p className="inline-error">{upload.error.message}</p>}</>;
}

export default function RecommendationDetailPage() {
  const recommendationId = String(useParams<{ recommendationId: string }>().recommendationId);
  const { scope } = useScope();
  const query = useQuery({ queryKey: ["recommendation", recommendationId, scope], queryFn: () => api.recommendation(recommendationId, scope) });
  if (query.isLoading) return <LoadingState label="Loading recommendation…" />;
  if (query.error || !query.data) return <ErrorState error={query.error} />;
  const record = query.data; const precheck = asRecord(record.precheck); const similar = asRecord(precheck.similar_works); const cost = asRecord(precheck.cost_comparison);
  return <>
    <header className="recommendation-header"><div><p className="eyebrow">Recommendation Record</p><h1>{record.title}</h1><p><strong>{record.recommendation_id}</strong> · {record.village}, {record.district}</p></div><span className={`status-badge status-${record.status.toLowerCase().replaceAll("_", "-")}`}>{record.status_label}</span></header>
    {record.runtime_checks.length > 0 && <div className="attention-strip"><AlertTriangle size={18} /><div><strong>Needs Attention</strong><p>{record.runtime_checks.map((item) => text(item.area)).join(" · ")}</p></div></div>}
    <ol className="lifecycle-tracker">{record.tracker.map((item) => <li className={item.state.toLowerCase()} key={item.key}><span>{item.state === "COMPLETE" ? <Check size={13} /> : ""}</span><strong>{item.label}</strong></li>)}</ol>
    <Section title="Work Details"><dl className="dossier-facts"><div className="dossier-fact"><dt>Purpose</dt><dd>{record.description}</dd></div><div className="dossier-fact"><dt>Public Benefit</dt><dd>{record.public_benefit}</dd></div><div className="dossier-fact"><dt>Sector</dt><dd>{record.sector}</dd></div><div className="dossier-fact"><dt>Work Type</dt><dd>{record.sub_sector}</dd></div><div className="dossier-fact"><dt>MP</dt><dd>{record.mp_name}</dd></div><div className="dossier-fact"><dt>Proposed Project Cost</dt><dd>{inr.format(record.proposed_project_cost_inr)}</dd></div>{record.sanctioned_cost_inr != null && <div className="dossier-fact"><dt>Sanctioned Cost</dt><dd>{inr.format(record.sanctioned_cost_inr)}</dd></div>}</dl></Section>
    <Section title="Location"><div className="location-card"><MapPin size={20} /><div><strong>{record.village}, {record.block}</strong><p>{record.district}, {record.state}{record.pincode ? ` · ${record.pincode}` : ""}</p><small>{record.latitude != null ? `${record.latitude}, ${record.longitude}` : "Coordinates not available"}</small></div></div></Section>
    <Section title="Pre-Check">{Object.keys(precheck).length ? <><div className="precheck-heading"><Check size={18} /><div><span>PRE-CHECK</span><strong>{text(precheck.overall_status)}</strong></div></div><div className="check-grid"><article><span>Similar Works</span><strong>{text(similar.summary)}</strong></article><article><span>Proposed Cost</span><strong>{text(cost.summary)}</strong></article><article><span>Location</span><strong>{text(asRecord(precheck.location_check).summary)}</strong></article><article><span>Rules</span><strong>{text(asRecord(precheck.applicable_rule_checks).summary)}</strong></article></div>{asRows(similar.items).length > 0 && <div className="similar-grid">{asRows(similar.items).map((item) => <article key={String(item.work_id)}><span>{text(item.label)}</span><Link href={`/works/${item.work_id}`}>{text(item.work_id)}</Link><strong>{text(item.title)}</strong><small>{text(item.location)}</small></article>)}</div>}</> : <EmptyState label="Pre-check not run." />}</Section>
    <Section title="Documents & Photos"><DocumentPanel id={record.recommendation_id} documents={record.documents} /></Section>
    {record.runtime_checks.length > 0 && <Section title="Alerts"><div className="warning-groups">{record.runtime_checks.map((item, index) => <article className={text(item.level) === "Strong Issue" ? "warning-card state-border-strong_issue" : "warning-card state-border-review"} key={index}><strong>{text(item.area)}</strong><p>{text(item.message)}</p></article>)}</div></Section>}
    <Section title="Review & Action"><ActionPanel key={scope.role} id={record.recommendation_id} status={record.status} /></Section>
    <Section title="Recent Activity" subtitle={record.activity.length ? `${record.activity.length} recorded ${record.activity.length === 1 ? "action" : "actions"} · latest first` : undefined}>{record.activity.length ? <div className="activity-list">{record.activity.slice().reverse().map((item) => <article key={String(item.event_id)}><div className="activity-marker" aria-hidden="true"><Check size={15} /></div><div className="activity-content"><div className="activity-head"><strong>{friendlyLabel(item.event_type)}</strong><time dateTime={text(item.timestamp)}>{activityTime(item.timestamp)}</time></div><p>{text(item.detail)}</p><small className="activity-meta"><UserRound size={12} />{text(item.actor_label)}</small></div></article>)}</div> : <EmptyState label="No recent activity." />}</Section>
    <div className="brief-actions"><Link className="button secondary" href={scope.role === "MP" ? "/my-works" : "/new-recommendations"}>Back to list</Link></div>
  </>;
}
