# 1. Day 9 Goal

Day 9 delivers **MPLADS Sentinel**, a local FastAPI + Next.js decision-support application over the frozen Day-2 through Day-8.2 intelligence artifacts. It adds governed role scoping, dashboards, a human-review queue, complete work dossiers, trend/hotspot views, guideline-grounded explanations, and append-only officer review/audit records. No model was retrained, no risk-fusion weight was changed, and no Day-10 deployment work was started.

# 2. Application Architecture

The application is a two-process local system:

1. FastAPI loads and validates frozen CSV/JSON artifacts once, retains one-row-per-work tables in memory, and indexes one-to-many evidence by `work_id`.
2. Next.js consumes bounded JSON APIs through one typed/Zod-validated client and caches requests with React Query.
3. Work details are fetched on demand; no 3,000-work detail payload is sent to the browser.
4. Officer actions are appended separately to runtime JSONL. Analytical artifacts remain immutable.
5. The existing Day-8 explanation service is lazy. Ordinary application navigation cannot call Groq.

# 3. Backend Stack

- Python 3.12.10 from `C:\SIH-PROJECT\.venv\Scripts\python.exe`
- FastAPI 0.141.1
- Uvicorn 0.52.4
- Pydantic 2.13.5 and pydantic-settings
- pandas 2.3.3
- orjson 3.12.0 installed as an approved Day-9 dependency
- Existing local Day-8 `httpx` Groq client; no provider SDK added

# 4. Artifact Repository

`ApplicationArtifactRepository` loads the governed work-level artifacts, queue, trend/hotspot tables, policy, guideline manifest/chunks, and all 3,000 explanation contexts at startup. It also creates read-only profile indexes from `03_works.csv`, `01_mp_master.csv`, and `02_agencies_vendors.csv` so descriptions, coordinates, MP names, and agency names are visible without modifying `Demo-data`.

Peer evidence, alerts, payment evidence, compliance evidence, predictive explanations, and corroborated duplicate pairs remain separate indexed collections. Payments and progress were not merged. Duplicate comparison uses only rows where Day-4.1 `review_candidate=true`.

# 5. Startup Integrity

Startup fails closed if a required artifact is absent; a core work-level table does not contain exactly 3,000 unique IDs; work-ID sets differ; grouped evidence references an unknown work; the risk-fusion policy version is absent; the guideline hash is absent; or the 3,000 explanation contexts do not align.

Nine unique work-level views are checked against the same work-ID set. Work-detail serving additionally verifies that the sum of contribution points reproduces the frozen Review Priority score.

Cold startup preloads tens of megabytes of governed evidence and may take materially longer than warm requests. This is deliberate prototype behavior to eliminate repeated CSV reads.

# 6. API Contracts

All application routes are versioned under `/api/v1`, except health and standard documentation:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Process and artifact health |
| GET | `/api/v1/meta` | Non-secret versions and governance metadata |
| GET | `/api/v1/scope/options` | Role, state, district, and MP selectors |
| GET | `/api/v1/dashboard/overview` | Scope-aware KPIs and observed conditions |
| GET | `/api/v1/review-queue` | Server-filtered/paginated HIGH/CRITICAL queue |
| GET | `/api/v1/works/{work_id}` | Complete, on-demand evidence dossier |
| GET | `/api/v1/trends` | Bounded selected trend series |
| GET | `/api/v1/hotspots` | Separate detector prevalence shares |
| GET | `/api/v1/alerts` | Scoped and filterable work-level early warnings |
| POST | `/api/v1/works/{work_id}/explain` | Local or explicit Groq explanation |
| POST | `/api/v1/works/{work_id}/reviews` | Append officer review and audit event |
| GET | `/api/v1/works/{work_id}/reviews` | Immutable review history |

The exported OpenAPI contract is `data/processed/application/openapi.json` (36,417 bytes at final generation). Swagger UI is enabled at `/docs`.

# 7. Demo Role Scoping

The backend enforces all demo scope rules:

- `MOSPI`: all 3,000 works.
- `STATE`: requires `state`.
- `DISTRICT`: requires both `state` and `district`.
- `MP`: requires `mp_id`.

Missing required scope fields return HTTP 422. Browser verification selected STATE / Andhra Pradesh and returned 485 works and 206 HIGH/CRITICAL review items. This is demonstrative filtering, not production identity or authorization.

# 8. Dashboard Overview

MOSPI-scope values verified in the live application:

- Works: 3,000
- Review queue: 1,104
- Mean Review Priority: 42.3 (display rounded; governed mean 42.2653)
- Observed overdue: 272
- Priority bands: LOW 567, MEDIUM 1,329, HIGH 1,096, CRITICAL 8
- Sanctioned: INR 5,557,508,000
- Released payments: INR 4,984,010,000
- Observed over-sanction: 20 works
- Duplicate review candidates: 24 works
- Payment evidence: 1,574 works
- Compliance review: 2,132 works

The dashboard labels Review Priority as deterministic triage, not probability or verdict.

# 9. Review Queue

The default queue contains the frozen 1,104 HIGH/CRITICAL works and sorts by Review Priority descending, then `work_id` ascending. The endpoint supports bounded page sizes up to 100, page number, text search, lifecycle, priority band, sector/sub-sector, alert type, duplicate/compliance flags, overdue/over-sanction flags, review status, and approved sort fields.

The frontend uses 25 rows per page, 300 ms debounced search, band/lifecycle filters, next/previous navigation, and current-page CSV export. Each compact row includes scope/profile fields, rank, score/band, top evidence, current officer status, and a bounded alert preview.

# 10. Work Detail

The dossier exposes profile/location/MP/agency data; recommended, estimated, sanctioned, released, and progress values; completion and asset/UC/handover/public-use/audit status; valid event timeline; priority score and all family contributions; early-warning alerts; anomaly and top-ten peer deviations; corroborated duplicate comparisons; payment and fund-progress evidence; every compliance rule; predictive serving context; trend context; deterministic explanation; and review history.

Live verification of `W-001937` showed Review Priority 89.441901. Contributions were COMPLIANCE 32, PAYMENT_EXECUTION 20, DUPLICATE_REVIEW 14.130249, OPERATIONAL_TREND_CONTEXT 9.160584, ANOMALY 7.900415, and PEER_DEVIATION 6.250653; their exact sum is 89.441901.

# 11. Detector Evidence Integration

Anomaly output is labeled within-lifecycle statistical unusualness, not a probability. Peer evidence is bounded to the ten strongest absolute robust deviations. Duplicate evidence renders only the single corroborated Day-4.1 candidate for the top case and labels it as a review candidate, never a confirmed duplicate. Payment and fund-progress results retain their source codes and explanatory text.

# 12. Compliance Integration

All eight Day-5 results for a work are shown, including PASS, REVIEW, INSUFFICIENT_DATA, NOT_APPLICABLE, and any deterministic NON_COMPLIANT evidence that exists. Rule title, observed/expected context, severity, guideline clause, and page remain visible. Compliance REVIEW is explicitly described as evidence needing verification, not non-compliance.

# 13. Predictive Integration

The UI distinguishes observed overdue/over-sanction conditions from prediction. Delay probabilities are never served as available: completed works show `OUTCOME_ALREADY_KNOWN`, while eligible execution use remains unavailable because no valid delay model was fitted. A permanent note states that delay prediction is unavailable.

Cost output uses only the governed raw-model serving score/percentile where applicable and displays `PROTOTYPE_WEAK_DISCRIMINATION`. Calibrated diagnostic output does not enter Review Priority.

# 14. Trend / Hotspot Integration

The trend API supports selected metric, group type, state/district/sector token, date bounds, role scope, and a hard response limit. The frontend chart loads only the selected view. Available metrics cover work recommendations, amounts, sanctions, payments, and progress reports.

Hotspots show separate unusualness, duplicate-review, payment-evidence, persistent-gap, observed-overdue, observed-over-sanction, and compliance-review shares. No composite hotspot score exists and hotspot prevalence never feeds an individual work score. State/district/sector comparison is available through group selection and scoped tables.

# 15. Groq + Fallback Integration

Work detail immediately renders the frozen deterministic fallback. Only `POST /api/v1/works/{work_id}/explain` with `{"use_llm": true}` enters the lazy Day-8 Groq path. No Day-9 live Groq call was made.

No-key, rate-limit, timeout, connection, malformed response, schema rejection, and grounding rejection behavior is covered by existing Day-8 tests; Day-9 additionally mocks a provider-service failure and verifies a safe `FALLBACK_SERVICE_UNAVAILABLE` response with no exception detail. Core pages, reviews, compliance, and trends are provider-independent.

# 16. Officer Review Workflow

Supported statuses are OPEN, IN_REVIEW, NEEDS_CLARIFICATION, ESCALATED, RESOLVED, and FALSE_POSITIVE. POST validates work, role, status, actor label, and note length. It appends one immutable record to `data/runtime/reviews.jsonl` and a corresponding event to `data/runtime/audit_log.jsonl` under a process lock.

The live browser test appended one `IN_REVIEW` integration record for `W-001937`, reloaded the dossier, displayed the new current status, and verified one review line and one audit line. Tests use temporary directories.

# 17. Frontend Stack

- Next.js 16.3.4, React/React DOM 19.2.8, TypeScript 5.9.3
- Tailwind CSS 4.3.3 plus a small semantic design system
- React Query 5.102.8
- Zod 4.5.4
- Recharts 3.10.1
- Lucide React 0.544.0

# 18. Frontend Routes

- `/`: overview dashboard
- `/review-queue`: paginated review queue
- `/works/[workId]`: complete work evidence dossier and workflow
- `/trends`: trend comparison and detector hotspots
- `/methodology`: feature coverage and interpretation guardrails
- `/_not-found`: friendly invalid-route state

All data shown on operational routes comes from the real FastAPI service. No mock dataset or hard-coded work record is used.

# 19. UI / UX Design

The interface uses a restrained navy/teal/saffron government-analytics palette, persistent navigation, clear hierarchy, accessible native labels, status text alongside color, responsive desktop/tablet/mobile breakpoints, bounded tables, loading/error/empty states, and no excessive animation. Browser DOM and visual checks passed at a 1280-pixel viewport with no horizontal document overflow and zero warning/error console entries.

# Feature Completeness Against SIH Problem Statement

| SIH requirement | Backend capability | Frontend component | Source / API | Status |
| --- | --- | --- | --- | --- |
| Sanctions | Profile and aggregate sums | Overview + work profile | `project_features.csv`; dashboard/work APIs | Complete |
| Cost estimates | Recommended/technical/sanction values | Work profile | `project_features.csv` | Complete |
| Expenditure | Released/final/current context | Overview + work payments | project features/work API | Complete |
| Payments | Separate aggregates/evidence index | Payments section | payment artifacts | Complete |
| Work progress | As-of physical/financial fields | Work profile/payments | project/fund-progress artifacts | Complete |
| Completion/assets | Completion and asset closure flags | Profile + compliance | project features/compliance | Complete |
| Anomalies/unusual patterns | Lifecycle-local score/percentile | Unusualness panel | anomaly API data | Complete |
| Peer deviations | Bounded robust peer evidence | Top-deviation cards | peer artifacts | Complete |
| Duplicate review | Corroborated candidates only | Paired comparison card | Day-4.1 candidates | Complete |
| Payment irregularities | Indexed evidence | Payment evidence cards | payment irregularities | Complete |
| Fund vs progress | Separate gap/persistence context | Fund-progress card | fund progress evidence | Complete |
| Observed cost overrun | Over-sanction facts | Dashboard/work prediction | project/predictive artifacts | Complete |
| Observed delay | Overdue facts | Dashboard/work prediction | project/predictive artifacts | Complete |
| Predictive cost warning | Weak raw serving context | Prediction panel | predictive scores/explanations | Complete with warning |
| Delay-model unavailability | Explicit no-model state | Prediction notice | predictive scores | Complete |
| Compliance monitoring | All rules and citations | Compliance cards | compliance evidence | Complete |
| Trend analysis | Bounded filtered series | Recharts trend view | `/api/v1/trends` | Complete |
| Hotspots | Separate transparent shares | Hotspot table | `/api/v1/hotspots` | Complete |
| Review-priority alerts | Scoped work alerts | Overview/work evidence | `/api/v1/alerts` + work API | Complete |
| Early warning | Observed/predictive separation | Queue/work sections | Day-7/Day-6 artifacts | Complete |
| MP dashboard | Required `mp_id` scope | Global selector | dashboard/queue APIs | Complete (demo scope) |
| District dashboard | State+district scope | Global selector | dashboard/queue/trend APIs | Complete (demo scope) |
| State dashboard | State scope | Global selector | dashboard/queue/trend APIs | Complete (demo scope) |
| MoSPI dashboard | National scope | Global selector | all core APIs | Complete (demo scope) |
| Decision support | Governed triage/evidence | Whole application | frozen artifacts | Complete |
| Human review | Validated append | Officer form/history | review APIs | Complete |
| Audit trail | Paired append-only event | Status/history confirmation | audit JSONL | Complete |
| Grounded AI explanation | Lazy Day-8 service | Explicit Groq button | explain API | Complete |
| Offline deterministic fallback | Precomputed local context | Default explanation | explanation context | Complete |

Core features are complete and manually reachable through the main flow. Advanced features implemented are the valid-event project timeline, state/district/sector comparison, current-page filtered queue export, and methodology help. Deferred items are MapLibre (no approved offline basemap/tile source, and network dependence would weaken demo resilience), chart-click queue drill-down (queue filters and chart group encodings do not yet share a complete reversible mapping), full-result CSV export (current-page export keeps payload bounded), and a separate SHAP visualization (raw explanatory fields are shown where applicable; a new visualization would add little while the cost model remains weak).

# 20. Security / Secret Handling

`.env` and frontend `.env.local` are ignored. The frontend contains only `.env.example` with `NEXT_PUBLIC_API_BASE_URL`; it has no provider credential variable. A content audit over backend source, frontend source excluding dependencies/build output, README/AGENTS, and generated application artifacts found zero credential-looking `gsk_` values and zero non-empty `GROQ_API_KEY` assignments. API metadata exposes the provider/model but no key, payload, prompt, or exception stack. CORS defaults to `http://localhost:3000`; wildcard origins are rejected.

All five prohibited adjudicative UI phrases defined by the Day-9 specification had zero source/generated hits.

# 21. Backend Tests

Thirteen Day-9 tests cover health/meta secrecy, four scopes and invalid scope rejection, queue pagination/order, detail reconciliation and bounded evidence, 404s, scoped work alerts, lazy deterministic explanation, safe explicit-provider failure, append-only reviews/audits, validation, and ground-truth absence from OpenAPI.

# 22. Frontend Build / Lint

`npm run lint` passed with zero errors/warnings. `npm run build` passed TypeScript checks and generated all six application routes. `npm install` reported zero known vulnerabilities.

# 23. Full Regression Test

Final result: **189 passed, 0 failed** in 131.10 seconds. One upstream Starlette deprecation warning notes future `httpx2` migration; it does not affect behavior. The suite includes all prior Day-1 through Day-8.2 regression and immutable-hash checks plus Day-9 tests.

# 24. Source / Artifact Integrity

All 12 `Demo-data` CSVs remain present and the pinned SHA-256 test passed. Frozen Day-2 through Day-8.2 tables, models, trend/fusion outputs, guideline assets, and Day-8 local index hashes were rechecked by the full suite and remained byte-identical. No earlier feature/detector/compliance/predictive/trend/RAG artifact was regenerated.

New generated analytical-interface output is confined to:

- `data/processed/application/openapi.json`
- `data/processed/application/day9_application_summary.json`

Runtime officer data is confined to `data/runtime`. `07_anomaly_ground_truth.csv` remains evaluation-only and is absent from repositories, OpenAPI, UI responses, and the production explanation path.

# 25. Known Limitations

- Data is synthetic and does not establish nationwide production validity.
- Role selection is demo scoping, not production authentication/authorization.
- CSV/JSON in-memory serving is appropriate for 3,000 prototype works, not final nationwide infrastructure.
- Cold startup is slower because all governed evidence is preloaded; representative warm single-request timings were overview 95.0 ms, queue 77.3 ms, work detail 12.0 ms, trends 47.6 ms, and hotspots 16.8 ms. These are local observations, not load-test guarantees.
- Runtime review JSONL is process-local and is not a multi-user transactional store.
- Groq is optional and rate-limited; fallback remains available.
- Delay prediction remains unavailable and cost-overrun prediction remains weak prototype evidence.
- Review Priority is an engineering policy, not a likelihood estimate of wrongdoing.
- The frontend supports decision support, not automatic enforcement.
- No public deployment, production identity provider, observability stack, or multi-instance coordination was added.

# 26. Local Run Instructions

From `C:\SIH-PROJECT`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal:

```powershell
Set-Location C:\SIH-PROJECT\code\frontend
npm install
npm run dev
```

Open `http://localhost:3000`; API docs are at `http://localhost:8000/docs`.

# 27. Recommended Day 10

**Final End-to-End Testing + Deployment + SIH Demo Polish.** Day 10 has not been started.
