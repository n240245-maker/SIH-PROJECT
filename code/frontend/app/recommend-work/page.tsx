"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, FileText, LocateFixed, MapPin, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { inr, text } from "@/lib/format";
import { asRecord, asRows } from "@/lib/presentation";
import { useScope } from "@/lib/scope";

type FormState = {
  title: string; sector: string; sub_sector: string; description: string; public_benefit: string;
  state: string; district: string; block: string; village: string; pincode: string;
  latitude: string; longitude: string; proposed_project_cost_inr: string;
  expected_duration_months: string; preferred_start_period: string;
};

const EMPTY: FormState = {
  title: "", sector: "", sub_sector: "", description: "", public_benefit: "",
  state: "", district: "", block: "", village: "", pincode: "", latitude: "", longitude: "",
  proposed_project_cost_inr: "", expected_duration_months: "", preferred_start_period: "",
};

async function encoded(file: File) {
  const buffer = await file.arrayBuffer();
  let binary = ""; const bytes = new Uint8Array(buffer); const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return window.btoa(binary);
}

export default function RecommendWorkPage() {
  const { scope } = useScope();
  const options = useQuery({ queryKey: ["scope-options"], queryFn: api.scopeOptions });
  const member = options.data?.mps.find((item) => item.mp_id === scope.mp_id);
  const [step, setStep] = useState(1); const [form, setForm] = useState<FormState>(EMPTY);
  const [supporting, setSupporting] = useState<File | null>(null); const [photo, setPhoto] = useState<File | null>(null);
  const [message, setMessage] = useState(""); const [recommendationId, setRecommendationId] = useState<string | null>(null);
  const [precheck, setPrecheck] = useState<Record<string, unknown> | null>(null); const [submitted, setSubmitted] = useState(false);
  const districts = useMemo(() => member?.districts ?? [], [member]);
  const availableSubSectors = options.data?.sub_sectors ?? [];
  const update = (key: keyof FormState, value: string) => setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (!member || form.state) return;
    // Scope options arrive asynchronously and initialize the read-only constituency fields once.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm((current) => ({ ...current, state: member.state_name ?? "", district: districts[0] ?? "" }));
  }, [member, districts, form.state]);

  const createAndCheck = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        ...form,
        pincode: form.pincode || null,
        latitude: form.latitude ? Number(form.latitude) : null,
        longitude: form.longitude ? Number(form.longitude) : null,
        proposed_project_cost_inr: Number(form.proposed_project_cost_inr),
        expected_duration_months: form.expected_duration_months ? Number(form.expected_duration_months) : null,
        preferred_start_period: form.preferred_start_period || null,
      };
      const created = await api.createRecommendation(scope, payload);
      const files = [
        supporting && { file: supporting, document_type: "SUPPORTING_DOCUMENT" },
        photo && { file: photo, document_type: "SITE_PHOTO" },
      ].filter(Boolean) as { file: File; document_type: string }[];
      for (const item of files) {
        await api.uploadRecommendationDocument(created.recommendation_id, scope, "MP Office", {
          document_type: item.document_type,
          original_filename: item.file.name,
          media_type: item.file.type,
          content_base64: await encoded(item.file),
          latitude: item.document_type === "SITE_PHOTO" && form.latitude ? Number(form.latitude) : null,
          longitude: item.document_type === "SITE_PHOTO" && form.longitude ? Number(form.longitude) : null,
        });
      }
      const checked = await api.precheckRecommendation(created.recommendation_id, scope);
      return { id: created.recommendation_id, checked };
    },
    onSuccess: ({ id, checked }) => { setRecommendationId(id); setPrecheck(checked); setMessage(""); },
  });
  const submit = useMutation({
    mutationFn: () => api.recommendationAction(recommendationId!, scope, { action: "SUBMIT", actor_label: "MP Office" }),
    onSuccess: () => setSubmitted(true),
  });

  const validate = () => {
    if (step === 1 && (!form.title.trim() || !form.sector || !form.sub_sector || form.description.trim().length < 10 || !form.public_benefit.trim())) return "Complete all work details before continuing.";
    if (step === 2 && (!form.state || !form.district || !form.block.trim() || !form.village.trim())) return "Complete the location details before continuing.";
    if (step === 2 && ((form.latitude && !form.longitude) || (!form.latitude && form.longitude))) return "Enter both latitude and longitude, or leave both blank.";
    if (step === 3 && !(Number(form.proposed_project_cost_inr) > 0)) return "Enter a valid proposed project cost.";
    if ([supporting, photo].some((file) => file && file.size > 10_000_000)) return "Each uploaded file must be no larger than 10 MB.";
    setMessage(""); return null;
  };
  const next = () => { const problem = validate(); if (problem) setMessage(problem); else setStep((value) => Math.min(4, value + 1)); };
  const locate = () => {
    if (!navigator.geolocation) { setMessage("Location access is not available in this browser."); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setForm((current) => ({ ...current, latitude: coords.latitude.toFixed(6), longitude: coords.longitude.toFixed(6) })),
      () => setMessage("Location could not be read. You can enter coordinates manually."),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  if (scope.role !== "MP") return <div className="state-box"><div><strong>MP Portal required</strong><p>Select MP in the role menu to recommend a work.</p></div></div>;
  if (options.isLoading) return <LoadingState label="Preparing the recommendation form…" />;
  if (options.error) return <ErrorState error={options.error} />;
  if (submitted && recommendationId) return <div className="success-page"><Check size={34} /><p className="eyebrow">Recommendation Submitted</p><h1>{recommendationId}</h1><p>Status: Recommended</p><div className="brief-actions"><Link className="button" href={`/recommendations/${recommendationId}`}>Track Work</Link><Link className="button secondary" href="/my-works">View My Works</Link></div></div>;

  const similar = asRecord(precheck?.similar_works); const cost = asRecord(precheck?.cost_comparison);
  return <>
    <div className="page-title"><div><p className="eyebrow">MP Portal</p><h1>Recommend Work</h1><p>Submit a work proposal to the District Authority for administrative review.</p></div></div>
    <div className="stepper" aria-label="Recommendation progress">{["Work Details", "Location", "Cost & Evidence", "Pre-Check"].map((label, index) => <div className={step === index + 1 ? "current" : step > index + 1 ? "complete" : ""} key={label}><span>{index + 1}</span><strong>{label}</strong><small>{index + 1} of 4</small></div>)}</div>
    <section className="panel recommendation-form">
      {step === 1 && <div className="form-grid"><label className="wide">Work Title<input required maxLength={180} value={form.title} onChange={(event) => update("title", event.target.value)} /></label><label>Sector<select required value={form.sector} onChange={(event) => update("sector", event.target.value)}><option value="">Select sector</option>{options.data?.sectors?.map((item) => <option key={item}>{item}</option>)}</select></label><label>Sub-Sector / Work Type<select required value={form.sub_sector} onChange={(event) => update("sub_sector", event.target.value)}><option value="">Select work type</option>{availableSubSectors.map((item) => <option key={item}>{item}</option>)}</select></label><label className="wide">Purpose / Short Description<textarea required minLength={10} maxLength={2000} value={form.description} onChange={(event) => update("description", event.target.value)} /></label><label className="wide">Expected Public Benefit<textarea required maxLength={1000} value={form.public_benefit} onChange={(event) => update("public_benefit", event.target.value)} /></label></div>}
      {step === 2 && <div className="form-grid"><label>State<input value={form.state} readOnly /></label><label>District<select required value={form.district} onChange={(event) => update("district", event.target.value)}><option value="">Select district</option>{districts.map((item) => <option key={item}>{item}</option>)}</select></label><label>Block<input required value={form.block} onChange={(event) => update("block", event.target.value)} /></label><label>Village / Locality<input required value={form.village} onChange={(event) => update("village", event.target.value)} /></label><label>Pincode<input inputMode="numeric" pattern="[0-9]{6}" value={form.pincode} onChange={(event) => update("pincode", event.target.value)} /></label><div className="location-action"><button type="button" className="button secondary" onClick={locate}><LocateFixed size={15} />Use Current Location</button></div><label>Latitude<input type="number" min="-90" max="90" step="any" value={form.latitude} onChange={(event) => update("latitude", event.target.value)} /></label><label>Longitude<input type="number" min="-180" max="180" step="any" value={form.longitude} onChange={(event) => update("longitude", event.target.value)} /></label>{form.latitude && form.longitude && <p className="wide location-readout"><MapPin size={15} />Site coordinates: {form.latitude}, {form.longitude}</p>}</div>}
      {step === 3 && <div className="form-grid"><label className="wide">Proposed Project Cost (₹)<input required type="number" min="1" step="1" value={form.proposed_project_cost_inr} onChange={(event) => update("proposed_project_cost_inr", event.target.value)} />{Number(form.proposed_project_cost_inr) > 0 && <small>{inr.format(Number(form.proposed_project_cost_inr))}</small>}</label><label>Expected Duration (months)<input type="number" min="1" max="120" value={form.expected_duration_months} onChange={(event) => update("expected_duration_months", event.target.value)} /></label><label>Preferred Start Period<input placeholder="Example: April–June 2027" value={form.preferred_start_period} onChange={(event) => update("preferred_start_period", event.target.value)} /></label><label className="upload-field"><FileText size={20} /><span>Supporting Document</span><input type="file" accept="application/pdf,image/jpeg,image/png" onChange={(event) => setSupporting(event.target.files?.[0] ?? null)} /><small>{supporting?.name ?? "PDF, JPG or PNG · maximum 10 MB"}</small></label><label className="upload-field"><Upload size={20} /><span>Site Photo</span><input type="file" accept="image/jpeg,image/png" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} /><small>{photo?.name ?? "JPG or PNG · maximum 10 MB"}</small></label></div>}
      {step === 4 && <div className="precheck-review"><h2>Review Recommendation</h2><dl className="review-summary"><div><dt>Work</dt><dd>{form.title}</dd></div><div><dt>Location</dt><dd>{form.village}, {form.district}</dd></div><div><dt>Proposed Project Cost</dt><dd>{Number(form.proposed_project_cost_inr) > 0 ? inr.format(Number(form.proposed_project_cost_inr)) : "Not available"}</dd></div><div><dt>Evidence</dt><dd>{[supporting, photo].filter(Boolean).length || "No files selected"}</dd></div></dl>{!precheck ? <button className="button" disabled={createAndCheck.isPending} onClick={() => createAndCheck.mutate()}>{createAndCheck.isPending ? "Checking…" : "Run Pre-Check"}</button> : <div className="precheck-results"><div className={`precheck-heading ${text(precheck.overall_status).toLowerCase().replaceAll(" ", "-")}`}><Check size={18} /><div><span>PRE-CHECK</span><strong>{text(precheck.overall_status)}</strong></div></div><div className="check-grid"><article><span>Similar Works</span><strong>{text(similar.summary)}</strong></article><article><span>Proposed Cost</span><strong>{text(cost.summary)}</strong></article><article><span>Location</span><strong>{text(asRecord(precheck.location_check).summary)}</strong></article><article><span>Required Details</span><strong>{text(asRecord(precheck.required_details).status)}</strong></article></div>{asRows(similar.items).length > 0 && <div><h3>Similar Works Nearby</h3><div className="similar-grid">{asRows(similar.items).map((item) => <article key={String(item.work_id)}><span>{text(item.label)}</span><Link href={`/works/${item.work_id}`}>{text(item.work_id)}</Link><strong>{text(item.title)}</strong><small>{text(item.location)}{item.distance_km != null ? ` · ${text(item.distance_km)} km away` : ""}</small><p>{inr.format(Number(item.cost_inr))}</p></article>)}</div></div>}<button className="button" disabled={submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? "Submitting…" : "Submit Recommendation"}</button></div>}</div>}
      {(message || createAndCheck.error || submit.error) && <p className="inline-error" role="alert">{message || createAndCheck.error?.message || submit.error?.message}</p>}
      <div className="form-actions">{step > 1 && !recommendationId && <button type="button" className="button secondary" onClick={() => setStep((value) => value - 1)}>Back</button>}{step < 4 && <button type="button" className="button" onClick={next}>Continue</button>}</div>
    </section>
  </>;
}
