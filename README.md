# TRACE-X KAVACH

MPLADS Monitoring & Management Platform

## Problem

MPLADS implementation spans work recommendations, sanctions, execution, payments, progress, completion, assets, and compliance. The prototype must identify unusual, inefficient, or non-compliant patterns for authorized review without treating an anomaly as proof of fraud.

## Product Goal

Provide a role-aware operational portal for monitoring MPLADS works, recommending new works, reviewing evidence, and recording authorized follow-up while preserving provenance and governance boundaries.

## Architecture Summary

The MVP uses immutable CSV inputs, validation and entity linking, separate lifecycle tables, one-row-per-work derived features, stage-aware intelligence modules, explainable risk fusion, and role-based outputs. Core detection must remain functional without a hosted explanation provider.

## CSV-First Data Design

The MVP uses pandas DataFrames rather than a database. MP, entity, work, payment, progress, and asset/compliance tables remain separate. One-to-many payment and progress histories must be aggregated before creating `df_project_features`, which must contain exactly one row per work.

## Lifecycle Intelligence

### Pre-Sanction

Peer-cost context, duplicate candidates, eligibility checks, and sanction-stage evidence.

### Execution

Payment patterns, financial-versus-physical progress, delay risk, overrun risk, and agency/vendor context.

### Completion

Completion consistency, final expenditure, asset records, utilization certificates, handover, audit, and closure evidence.

### Cross-Project Trends

State, district, sector, agency, vendor, and time-based comparisons and hotspots.

## AI / ML Components

- Isolation Forest
- Robust peer statistics
- XGBoost / Random Forest
- Duplicate semantic similarity
- Deterministic compliance
- Risk fusion
- Groq-hosted, guideline-grounded RAG explanation

These are planned components. No model performance metrics are claimed.

## Repository Structure

- `code/intelligence/`: lifecycle intelligence and risk modules
- `code/backend/`: FastAPI application and governed artifact-serving layer
- `code/frontend/`: Next.js App Router monitoring and review interface
- `code/models/`: future model artifacts/contracts
- `code/rag/`: future guideline retrieval and explanation source
- `code/tests/`: future tests
- `Demo-data/`: read-only source CSVs
- `data/processed/`: generated CSV/JSON outputs
- `data/runtime/`: isolated append-only recommendation, review, activity, and upload state
- `guidelines/`: guideline source documents
- `docs/reference/`: supporting reference documents

## Important Data Rules

- `Demo-data/` is read-only.
- `07_anomaly_ground_truth.csv` is evaluation-only and must never provide production/model features.
- Keep payments and progress as separate one-to-many tables.
- Never train or score on a naive works/payments/progress expansion.
- Anomaly is not fraud; risk score is review priority; authorized humans decide.
- Do not introduce a database into the CSV-first MVP without explicit approval.

## Current Development Status

Day 0 through Day 9 and the intermediate safety audits are complete. The current local-only pre-Day-10 upgrade adds the operational MP-to-District recommendation workflow and role-specific officer navigation. This worktree has not been deployed as part of the upgrade.

### Operational Recommendation Workflow

- MPs can draft a recommendation, record its location and proposed cost, upload supporting evidence, run a bounded pre-check, submit it, and track its status.
- District Authorities can review scoped recommendations, request clarification, accept them for processing, add sanction details, record progress and payments, and mark work completion.
- Recommendation IDs are assigned sequentially and lifecycle activity is append-only.
- Runtime records and uploads stay under `data/runtime`; frozen analytical CSVs, models, rules, and evaluation artifacts remain read-only.
- Similar-work and cost comparisons are review support only. They never confirm duplication, approve a work, or replace authorized human decisions.

The local `feature/sih-final-enhancements` branch adds a fresh synthetic demo-v2
profile without changing the reproducible P0 baseline. It includes versioned
synthetic lifecycle and geo-evidence data, v2 model evaluation, authoritative
five-role scope, role-specific dashboards, a nine-section officer dossier, and a
deterministic nine-section case report. See
[docs/FINAL_SIH_ENHANCEMENT_IMPLEMENTATION.md](docs/FINAL_SIH_ENHANCEMENT_IMPLEMENTATION.md).
Day 2 provides a leakage-aware unified project profile, independent as-of lifecycle
aggregations, a one-row-per-work feature snapshot, and an audited feature catalog.
Day 3 provides robust lifecycle-aware peer benchmarks, three independent lifecycle
Isolation Forest detectors, within-stage rankings, statistical evidence, persisted
model metadata, and an isolated same-synthetic-snapshot diagnostic evaluation.
Day 4 provides local semantic duplicate-work candidates, deterministic payment
irregularity evidence, fund-versus-physical-progress reconciliation, and persistent
reported-gap evidence. These remain independent detector outputs.
Day 5 provides a verified/versioned MPLADS Guidelines 2023 source manifest,
page-aligned local text chunks, a manually encoded deterministic compliance-rule
registry, clause-linked evidence, and one-row-per-work compliance summaries. Rule
outcomes remain human-review evidence and are not a fused risk score.
Day 6 provides leakage-safe 25/50/75% historical landmark reconstruction,
work-level supervised splitting, a feasible calibrated cost-overrun XGBoost model
with Random Forest baseline and non-causal SHAP evidence, and current execution
early-warning scores. The delay target is explicitly unfitted because only 22
eligible negative outcomes exist, below the governed 50-work minimum.
Day 7 provides causal complete-month operational trends, separate detector
hotspots, work-level operational context, and fixed lifecycle-aware review-priority
fusion with reconstructable family contributions. Hotspot prevalence never feeds
back into work scores, calibrated cost output is excluded, and delay contributes
no model signal.
Day 8 provides a local 61-chunk guideline embedding index, direct-clause-first
retrieval, minimized frozen evidence bundles, strict structured output, grounding
and language validation, and a deterministic offline fallback. Day 8.1 configures
GroqCloud with `openai/gpt-oss-120b` through `/chat/completions`. The hosted model
is an optional on-demand explanation layer only; it never recalculates risk or
compliance, and the normal runner makes no external API call.

## Day 1 Commands

Run validation from the project root with the project Python 3.12 environment:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.data.validation
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Generated validation files are written only to `data/processed/`.

## Day 2 Commands

Build the controlled runtime feature snapshot:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.features.builder
```

This creates `data/processed/project_features.csv` and
`data/processed/feature_catalog.json`. The CSV is a runtime as-of snapshot, not an
automatically valid supervised training dataset.

Audit numeric/boolean feature distributions without labels or rewriting the
feature snapshot:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.features.quality
```

This refines the catalog's current generic-anomaly candidate metadata and writes
`data/processed/feature_quality_profile.json`.

## Day 3 Commands

Generate production anomaly artifacts without evaluation labels:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.anomaly.runner
```

Only after production models, metadata, scores, and summaries exist, run the
evaluation-only same-synthetic-snapshot diagnostic:

```powershell
.\.venv\Scripts\python.exe -m intelligence.anomaly.evaluation
```

Anomaly scores mean statistically unusual relative to comparable records. They
are not probabilities, compliance determinations, or automated verdicts. The peer
detector remains separate from Isolation Forest scoring; no Day-3 output is a fused
risk score.

## Day 4 Command

Generate the independent Day-4 duplicate, payment, and execution evidence:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.execution.runner
```

The first run downloads `sentence-transformers/all-MiniLM-L6-v2` into the local
project model cache. Project text is embedded locally and is not sent to an
external model API. `duplicate_candidate`, payment signals, and fund-progress
heuristics mean review evidence only; none is a final risk score or decision.

## Day 5 Command

Generate the deterministic compliance and guideline-foundation artifacts:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.compliance.runner
```

Compliance is decided only by the manually verified Python rules. The local
guideline extraction does not use OCR, embeddings, or an external text service.

## Day 6 Command

Generate Day-6 historical modelling, evaluation, model-registry, and current
early-warning artifacts:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.predictive.runner
```

The delay outcome is currently infeasible under the governed 50-positive / 50-
negative minimum and is not fitted. Cost-overrun probabilities are predictive
review context, not fraud probabilities or final fused risk scores.

## Day 7 Command

Generate Day-7 operational trends, hotspot context, review-priority evidence,
scores, queue, alerts, policy, and summary artifacts:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.risk_fusion.runner
```

The score is deterministic review priority under prototype policy v0.1. It is not
a probability or verdict. Detector-hotspot prevalence is never used in individual
scores.

## Day 8 Command

Generate the local guideline index, retrieval audit, and 3,000 deterministic
explanation contexts without calling an external API:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m rag.runner
```

An optional bounded live integration smoke test is available only when
`GROQ_API_KEY` is configured and `--live-smoke` is explicitly supplied. It uses at
most three cases, preflights access to the approved model, and sends
`tool_choice=none` with no tools or external search. The 3,000 context records are
local fallback and provenance records, not 3,000 hosted-model responses.

## Day 9 Local Application

Install the Python project into the existing Python 3.12 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Start the API from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The API is available at `http://localhost:8000`, with interactive documentation
at `http://localhost:8000/docs`. Frozen analytical artifacts are loaded and
validated once at startup. The first cold startup can therefore take longer than
subsequent API requests.

In a second terminal, install and start the frontend:

```powershell
Set-Location .\code\frontend
npm install
npm run dev
```

Open `http://localhost:3000`. To use another API origin, copy `.env.example` in
`code/frontend` to `.env.local` and edit `NEXT_PUBLIC_API_BASE_URL`. Never place
`GROQ_API_KEY` or another secret in a frontend environment variable.

The default work explanation is the frozen deterministic fallback. Groq is called
only after an explicit **Generate Grounded AI Explanation** action. Review records and their
corresponding audit events are append-only local JSONL under `data/runtime/`.

Day 9.1 organizes Work Detail as an officer investigation flow with centralized
friendly labels, evidence-governed field highlighting, explicit observed-versus-
predictive language, and optional technical details. A case-review support PDF is
available at `GET /api/v1/works/{work_id}/case-report.pdf`. Downloading it never
calls Groq: it uses the deterministic explanation unless an exact, already
validated Groq response is present in the process-local safe cache. The PDF is a
prototype decision-support document, not an official order or audit finding.

Day 9.2 adds lifecycle-aware Records & Completion Readiness, natural Attention
Level counts and filters, a separate actionable Requires Review flag, magnitude-
aware financial presentation, plain-language peer/trend cards, and a structured
AI-Assisted Case Assessment. These are presentation changes only: the frozen
Review Priority and Day-0 through Day-8.2 intelligence remain unchanged.

Verification commands:

```powershell
.\.venv\Scripts\python.exe -m pytest
Set-Location .\code\frontend
npm run lint
npm run build
```
