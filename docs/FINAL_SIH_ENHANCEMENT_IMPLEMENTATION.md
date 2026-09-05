# MPLADS Sentinel Synthetic Demo-v2

## Purpose and status

This branch adds a local, versioned demonstration profile for SIH26102 while
keeping the P0 baseline reproducible. It is decision-support software: an
anomaly, irregularity, duplicate candidate, early warning, or Review Priority
score is not a finding of fraud or wrongdoing. Authorized officials retain the
final decision.

All demo-v2 data, coordinates, evidence images, labels, comparisons, and model
evaluations are synthetic. Their distributions do not represent national
MPLADS prevalence or Government field evidence.

## Profiles and paths

- `MPLADS_DATASET_PROFILE=baseline` preserves the existing P0 runtime.
- `MPLADS_DATASET_PROFILE=demo_v2` selects the enhanced profile.
- `NEXT_PUBLIC_MPLADS_DATASET_PROFILE=demo_v2` selects `/api/v2` in the local
  frontend; the branch defaults to demo-v2 when the variable is absent.
- Source-like generated input: `data/Demo-data-v2/`.
- Derived work-level intelligence: `data/processed-v2/`.
- Retrained model artifacts: `models/v2/`.
- Append-only local site-evidence runtime: `data/runtime/site-evidence/`.

The root `Demo-data/`, baseline `data/processed/`, and baseline model/rule
artifacts are not rewritten by either v2 command.

## Reproducible local commands

Run these from `C:\SIH-PROJECT` with the existing Python 3.12 environment:

```powershell
$env:PYTHONPATH = 'C:\SIH-PROJECT\code'
.\.venv\Scripts\python.exe scripts\generate_demo_v2.py
.\.venv\Scripts\python.exe scripts\build_demo_v2_intelligence.py
```

The generator uses seed `26102`, an as-of date of `2026-09-05`, and stable
ordering and timestamps. `data/Demo-data-v2/00_manifest.csv` records row counts,
purposes, and SHA-256 checksums. `data/processed-v2/manifest.json` performs the
same function for processed and model artifacts.

## Synthetic schema

| File | Grain and purpose |
| --- | --- |
| `01_mp_master.csv` | One row per synthetic MP/constituency scope. |
| `02_entities.csv` | One row per synthetic implementing agency. |
| `03_works.csv` | One row per work, including lifecycle and synthetic registered location. |
| `04_payments.csv` | One-to-many payment history; never naively merged with progress. |
| `05_progress.csv` | One-to-many monthly progress history. |
| `06_assets.csv` | Zero-to-many asset records; the implementation supports multiple assets per work. |
| `10_work_records.csv` | Normalized lifecycle records, certificates, evidence, and verification states. |
| `11_annual_allocations.csv` | Financial-year, state, district, constituency, and MP aggregates. |
| `12_geo_site_evidence.csv` | Seeded, clearly labelled synthetic geo-site evidence. |
| `evaluation/anomaly_ground_truth_v2.csv` | Evaluation-only anomaly and duplicate helper labels. |

The operational loader never loads the evaluation file. Only the isolated
evaluation accessor may read it, and only `work_id` is used for alignment. The
labels do not enter training features, serving records, API contracts, frontend
state, explanations, compliance, or Review Priority.

## Lifecycle and normalized records

The generated works cover `PRE_SANCTION`, `EXECUTION`, and `COMPLETION`.
Completion records are neutral/not applicable before completion. Completed
works intentionally include a majority with usable closure evidence and a
controlled mix of missing, review, and insufficient-data cases. Supported
record types include sanction and progress records, payment support,
completion certificates, utilization certificates, handover, public-use
evidence, completed-work photographs, asset-register evidence, audit records,
and inspection reports.

## Geo-tagged progress evidence

The prototype calendar treats Monday-Friday as working days and may exclude an
explicitly supplied holiday list. It does not claim to contain official State
holiday calendars.

- An execution work expects one monthly site image during the first three
  working days of each month.
- Before execution, baseline evidence can be recorded.
- Completion evidence is due within three working days after the recorded
  completion date; counting begins on the following day.
- Monthly evidence stops after completion.
- States are `RECORDED`, `UPCOMING`, `DUE`, `OVERDUE`, and `NOT_APPLICABLE`.
- Missing or late evidence is a deterministic `Requires Review` warning and
  contributes exactly zero Review Priority points in v2.

The IA workflow captures image bytes, device coordinates, browser timestamp,
reporting month, stage, progress, provenance (`LIVE_SITE_CAPTURE` versus
`UPLOADED_IMAGE`), and an optional note. The backend computes SHA-256. A hash
supports stored-file integrity; it does not prove image authenticity. EXIF,
when present, is separate provenance.

When synthetic registered coordinates exist, Haversine distance is compared
with the configurable 500-metre prototype threshold. Results are Location
Consistent or Location Requires Review. If either coordinate is unavailable,
comparison is unavailable and the work is not penalized. The threshold is an
engineering configuration, not an MPLADS rule.

Only the assigned IA can submit evidence. Only the in-scope District Authority
can verify a runtime submission. MP, State, and MoSPI views are read-only.

## Fund and historical formulas

- Fund utilization percentage = recorded expenditure / sanctioned amount × 100.
- Financial progress and physical progress remain separate observations.
- Release above visible sanction, actual expenditure above sanction, and
  predicted early warning remain distinct.
- Previous-year comparisons are computed from `11_annual_allocations.csv`.
  The UI displays Comparison unavailable when the required rows are absent.
- Map/table views aggregate only records inside the authoritative scope. No
  external GeoJSON, live map API, or third-party map license is used; the
  accessible table is an honest fallback over synthetic coordinates.

## Cost-overrun modelling

The deterministic observed condition is:

`final_actual_expenditure_inr > sanctioned_amount_inr`

The predictive signal is a separate execution-stage Cost Overrun Early Warning.
Training snapshots are reconstructed for completed works using information
available before the final outcome. Work IDs are separated across train,
validation, and test. Prohibited predictors include final expenditure, actual
completion, scenario tags, target-derived fields, anomaly labels, and duplicate
helper labels.

Logistic Regression, Random Forest, and XGBoost are evaluated with fixed seeds.
Selection uses validation evidence and is reported with ROC-AUC, PR-AUC,
precision, recall, F1, Brier score, threshold, and confusion matrix. Calibration
is applied only if supported. Results are Synthetic Holdout Evaluation, not
real-world performance, fraud probability, or a production guarantee.

## Anomaly and peer intelligence

Three independent Isolation Forests serve `PRE_SANCTION`, `EXECUTION`, and
`COMPLETION`. Each lifecycle uses only its explicit feature schema. Robust peer
deviation remains independent supporting evidence. Evaluation labels are read
only after production scoring. The main officer view says what is unusual;
optional technical details explain the lifecycle model, percentile, peer
context, version, and the limitation that unusualness is not fraud.

## Duplicate retrieval

Descriptions are embedded locally with
`sentence-transformers/all-MiniLM-L6-v2`. Normalized embeddings use bounded
top-k nearest-neighbour retrieval rather than an all-pairs materialization.
Candidate policy also requires supporting sector, amount, and synthetic
location evidence. Near-neighbours that do not satisfy corroboration remain
non-candidates. Results are Duplicate Work Candidates for human comparison,
never confirmed duplicates.

## Deterministic controls and Review Priority

Payment chronology, observed delay, observed cost overrun, records/compliance,
and geo deadlines are deterministic. Groq does not calculate any of them.
Observed delay means that expected completion has passed and the work is not
completed; no delay-probability classifier is exposed.

Policy `REVIEW_PRIORITY_POLICY_V0_1_DEMO_V2` retains lifecycle-specific capped
families, reduces repeated evidence within a family, prevents duplicate counting,
and keeps the weak predictive cost signal secondary. Its v2 completion budget is
Anomaly 5%, Peer Deviation 5%, Duplicate Review 10%, Payment Execution 10%,
Observed Conditions 50%, and Compliance 20%. This explicit revision fixes the
baseline-style omission of deterministic final-cost evidence from completed-work
priority: a proven observed overrun now dominates statistical context without
being counted in another family. Geo evidence is warning-only and adds zero
points. Review Priority is triage for human review, not a probability or verdict.

## Authoritative role scope

FastAPI applies role scope to dashboards, queues, work detail, reports,
explanations, geo evidence, reviews, alerts, and maps/tables:

- MP: the selected `mp_id` and constituency.
- IA: the selected `agency_id` and assigned works.
- District: the selected state and district.
- State: the selected state.
- MoSPI: the synthetic national profile.

The frontend selector is not the security boundary. Missing role keys are
rejected, and out-of-scope work access returns the safe project-standard not-found
response. A production system must replace this demonstration selector with
authenticated RBAC and official identity claims.

## Officer interface

The work dossier follows this nine-section investigation flow:

1. Project Details
2. Monitoring Health
3. Anomalies & Irregularities
4. Key Risk Areas
5. Progress & Schedule
6. Geo-Tagged Progress Evidence
7. Records & Completion Readiness
8. AI-Assisted Case Explanation
9. Officer Review & Corrective Action

The desktop uses a fixed navy sidebar, with a compact responsive header on
mobile. Tables are scroll-contained, two-column areas collapse, the odd anomaly
card spans the row, disclosures are keyboard-accessible, focus is visible, and
every semantic color is accompanied by text.

Dashboards answer a role-specific operational question and preserve the required
MP, IA, District, State, and MoSPI section ordering. Morning briefs are structured
and deterministic by default.

## Groq and deterministic reports

Ordinary navigation, dashboards, work detail, review actions, geo workflows, and
PDF downloads make no Groq request. Groq is contacted only by an explicit
Generate Grounded AI Explanation action. The existing provider boundary remains
bounded, grounded, tool-free, and safe-fallback capable. Credentials stay server
side and are absent from API payloads, frontend files, reports, and logs.

The case-review PDF uses structured backend evidence and the local deterministic
explanation. Its nine sections mirror the dossier. It never calls Groq and labels
synthetic evidence clearly.

## Current limitations and production evolution

- All v2 evidence and holdout evaluation are synthetic.
- The anomaly holdout result is weak and must be treated as unusualness context.
- The cost model is promising only on the same synthetic generation regime; it
  requires external, temporal, official-data validation before production use.
- The CSV-first runtime has no authenticated identity provider, transactional
  database, durable object store, official holiday calendar, scheduled ingestion,
  managed model registry, or persistent vector service.
- Seeded SVGs demonstrate evidence presentation, not real site authenticity.
- The accessible aggregate map fallback has no national boundary geometry.

A production path is: official MPLADS/PFMS feeds → scheduled validated pipelines
→ governed warehouse/database → Government-approved object storage → authenticated
RBAC → official holiday calendars → managed model/vector registry → persistent
append-only review and audit services.
