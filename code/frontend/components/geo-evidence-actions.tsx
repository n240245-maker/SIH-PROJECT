"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, LocateFixed, Upload } from "lucide-react";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api";
import { useScope } from "@/lib/scope";

function currentMonth() { return new Date().toISOString().slice(0, 7); }

export function GeoEvidenceActions({ workId, items }: { workId: string; items: Record<string, unknown>[] }) {
  const { scope } = useScope();
  const queryClient = useQueryClient();
  const [sourceType, setSourceType] = useState<"LIVE_SITE_CAPTURE" | "UPLOADED_IMAGE">("LIVE_SITE_CAPTURE");
  const [stage, setStage] = useState("MONTHLY_PROGRESS"); const [month, setMonth] = useState(currentMonth());
  const [progress, setProgress] = useState("0"); const [officer, setOfficer] = useState(""); const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null); const [position, setPosition] = useState<{ latitude: number; longitude: number } | null>(null);
  const [positionError, setPositionError] = useState("");
  const locate = () => {
    setPositionError("");
    if (!navigator.geolocation) { setPositionError("This browser does not provide geolocation."); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setPosition({ latitude: coords.latitude, longitude: coords.longitude }),
      () => setPositionError("Location permission is required for field evidence."),
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 0 },
    );
  };
  const create = useMutation({
    mutationFn: async () => {
      if (!file || !position) throw new Error("Choose an image and capture the device location first.");
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("The image could not be read.")); reader.readAsDataURL(file);
      });
      const mediaType = file.type === "image/png" || file.type === "image/webp" ? file.type : "image/jpeg";
      return api.createGeoEvidence(workId, scope, {
        evidence_stage: stage, reporting_month: month, physical_progress_pct: Number(progress),
        latitude: position.latitude, longitude: position.longitude, capture_timestamp: new Date().toISOString(),
        captured_by_user: officer, source_type: sourceType, image_base64: dataUrl.split(",")[1], image_media_type: mediaType, note,
      });
    },
    onSuccess: async () => { setFile(null); setNote(""); await queryClient.invalidateQueries({ queryKey: ["v2-work", workId] }); },
  });
  const verify = useMutation({
    mutationFn: (evidenceId: string) => api.verifyGeoEvidence(evidenceId, scope, { verification_status: "DISTRICT_VERIFIED", verified_by: officer, note: "Verified by the District Authority." }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["v2-work", workId] }); },
  });

  if (scope.role === "IA") {
    const submit = (event: FormEvent) => { event.preventDefault(); create.mutate(); };
    return <form className="geo-capture" onSubmit={submit}><div className="geo-capture-head"><Camera size={19} /><div><strong>Submit geo-tagged site evidence</strong><p>Only the assigned Implementing Agency can submit. Location and timestamp are captured at submission.</p></div></div>
      <div className="form-grid"><label>Evidence source<select value={sourceType} onChange={(event) => setSourceType(event.target.value as typeof sourceType)}><option value="LIVE_SITE_CAPTURE">Live site capture</option><option value="UPLOADED_IMAGE">Uploaded image</option></select></label><label>Evidence stage<select value={stage} onChange={(event) => setStage(event.target.value)}><option>BEFORE_WORK</option><option>MONTHLY_PROGRESS</option><option>COMPLETION</option></select></label><label>Reporting month<input type="month" required value={month} onChange={(event) => setMonth(event.target.value)} /></label><label>Physical progress (%)<input type="number" min="0" max="100" step="0.1" required value={progress} onChange={(event) => setProgress(event.target.value)} /></label><label>Officer / field user<input required minLength={2} maxLength={120} value={officer} onChange={(event) => setOfficer(event.target.value)} /></label><label className="wide">Field note<textarea maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label><label className="wide image-input">{sourceType === "LIVE_SITE_CAPTURE" ? <Camera size={17} /> : <Upload size={17} />}<span>{sourceType === "LIVE_SITE_CAPTURE" ? "Open camera" : "Choose existing image"}</span><input type="file" accept="image/jpeg,image/png,image/webp" capture={sourceType === "LIVE_SITE_CAPTURE" ? "environment" : undefined} required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label></div>
      <div className="geo-submit-row"><button type="button" className="button secondary" onClick={locate}><LocateFixed size={15} />Capture current location</button><span>{position ? `${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}` : "No location captured"}</span><button className="button" disabled={create.isPending}>{create.isPending ? "Saving evidence…" : "Submit append-only evidence"}</button></div>
      {(positionError || create.error) && <p className="inline-error" role="alert">{positionError || create.error?.message}</p>}{create.isSuccess && <p className="success-inline" role="status"><CheckCircle2 size={14} />Evidence stored with a SHA-256 integrity hash.</p>}
      <p className="section-note">Uploaded files are clearly marked as uploads. Browser submission time is not claimed to be the original camera capture time.</p>
    </form>;
  }

  if (scope.role === "DISTRICT") {
    const pending = items.filter((item) => !String(item.source_type).startsWith("SEEDED_") && String(item.verification_status) !== "DISTRICT_VERIFIED");
    return <div className="district-verification"><label>District verifier name<input value={officer} minLength={2} onChange={(event) => setOfficer(event.target.value)} placeholder="Required to verify" /></label>{pending.map((item) => <button key={String(item.evidence_id)} className="button secondary" disabled={officer.trim().length < 2 || verify.isPending} onClick={() => verify.mutate(String(item.evidence_id))}><CheckCircle2 size={15} />Verify {String(item.evidence_id)}</button>)}{!pending.length && <p>No unverified local submissions are in this work.</p>}{verify.error && <p className="inline-error" role="alert">{verify.error.message}</p>}</div>;
  }
  return null;
}
