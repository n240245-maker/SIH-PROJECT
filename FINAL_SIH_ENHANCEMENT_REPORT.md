# Final SIH Enhancement — Local Acceptance Report

Date: 2026-09-05

Project: MPLADS Sentinel — SIH26102

Implementation status: **LOCAL IMPLEMENTATION COMPLETE — USER REVIEW REQUIRED**

## 1. Repository and deployment safety

- Local branch: `feature/sih-final-enhancements`
- Starting P0 commit: `574f9ef` (`Fix P0 mobile overflow`)
- The tracked tree was verified against `574f9ef` before implementation.
- No reverted P1 commit was restored, cherry-picked, or reused.
- No commit, push, deployment, deployment tag, production-variable change, or production-URL change was performed.
- The unrelated untracked `uv.lock` was not added, edited, deleted, or used.
- All Python work used `C:\SIH-PROJECT\.venv\Scripts\python.exe` (Python 3.12); `uv run`, the system Python 3.14, and the private Codex runtime were not used.

## 2. Files changed

### Data, intelligence, and scripts

- `code/intelligence/v2/__init__.py`
- `code/intelligence/v2/geo.py`
- `code/intelligence/v2/generator.py`
- `code/intelligence/v2/loader.py`
- `code/intelligence/v2/pipeline.py`
- `scripts/generate_demo_v2.py`
- `scripts/build_demo_v2_intelligence.py`
- `scripts/generate_v2_case_report.py`
- `code/tests/test_final_v2_enhancements.py`
- `data/Demo-data-v2/**`
- `data/processed-v2/**`
- `models/v2/**`

### Backend

- Added `code/backend/authorization.py`.
- Added `code/backend/reports/v2_case_review.py`.
- Added `code/backend/repositories/geo_evidence.py`.
- Added `code/backend/repositories/v2_artifacts.py`.
- Added `code/backend/routers/v2.py`.
- Added `code/backend/services/v2_application.py`.
- Updated backend configuration, dependency wiring, application routes, explanation routes, review routes, system routes, schemas, repositories, services, and app startup for profile-aware v2 serving.

### Frontend

- Added `code/frontend/components/geo-evidence-actions.tsx`.
- Updated the dashboard, review queue, alerts, trends, methodology, work dossier, shell, scope selector, API client, types, configuration, and shared styles.
- Fixed ordinary GET requests so they do not add an unnecessary JSON content type and therefore do not trigger avoidable browser CORS preflights.

### Configuration and documentation

- Updated `.env.example`, `.gitignore`, and `README.md`.
- Added `docs/FINAL_SIH_ENHANCEMENT_IMPLEMENTATION.md`.
- Added this acceptance report.

No files under `Demo-data`, `data/processed`, or the baseline governed model/rule locations were changed.

## 3. Versioned synthetic demo data

The v2 dataset is reproducible with seed `26102`, is explicitly marked `synthetic_demo_data=true`, and is isolated from the P0 source data.

> **SYNTHETIC DEMO DATA:** The records, distributions, site coordinates, evidence, and holdout metrics are generated for prototype testing. They do not represent real MPLADS national prevalence, official Government evidence, or real-world model performance.

### New source-like data

| File | Rows | SHA-256 |
|---|---:|---|
| `01_mp_master.csv` | 18 | `c5a0628d317992d6179ce1d5cea32c663707ee0edf316e895dd886ff522f1827` |
| `02_entities.csv` | 54 | `d67fb10aefffe3c61239f048332f2be4d1b8b2fa42b967c45ff3ecc9fbfa3d38` |
| `03_works.csv` | 5,000 | `26a404237171e4fec774492fdfd3855e8391896fa17becc2d0674f5fe0e9dbdd` |
| `04_payments.csv` | 16,760 | `962c43f2bd4722adf2913c336e2c008e4c4f657c7e68a4cfe122f68fc54d98da` |
| `05_progress.csv` | 90,905 | `63614549b48043b2813f731d4eff5fce505feed5a5a70c8c66ae4cf8463be5cf` |
| `06_assets.csv` | 2,604 | `2412cc980a8c558d073d84b0d33a7d8eba112907527d004bd0f8e720819d75bd` |
| `10_work_records.csv` | 43,908 | `ac353355f8fdafd121cebafec82e27053155f833004f5e65afb9573ef1d82c95` |
| `11_annual_allocations.csv` | 54 | `d0e8f53b68799accbd84277d18482c9a9ccccbb8d9ad328e00bb22c6788b97eb` |
| `12_geo_site_evidence.csv` | 19,442 | `a7791ed1d4b92a1bd53f0c3e392918a061408e69e99e50042b525f815b923487` |
| `evaluation/anomaly_ground_truth_v2.csv` | 5,000 | `92ae24a2bab2ad10a4ae24d88c07e51aaf5fd51bc10e185afc01d944e2d9412b` |

Three clearly labelled synthetic evidence SVGs are also included. Exact checksums for every source, generated artifact, and model are recorded in:

- `data/Demo-data-v2/00_manifest.csv`
- `data/processed-v2/manifest.json`

Integrity verification passed: all manifest hashes, declared row counts, primary keys, foreign keys, and one-row-per-work outputs are valid. Payments, progress, assets, records, and geo evidence remain separate one-to-many tables; no giant works/payments/progress merge was introduced.

## 4. Representative demo cases

| Scenario | Work ID |
|---|---|
| Normal work | `W-000101` |
| Observed delay | `W-000202` |
| Fund-utilization mismatch | `W-000303` |
| Payment chronology irregularity | `W-000404` |
| Observed cost overrun | `W-000505` |
| Cost-overrun early warning without observed overrun | `W-000606` |
| Duplicate candidate pair | `W-000707`, `W-000708` |
| Missing monthly geo evidence | `W-000808` |
| Late geo evidence | `W-000909` |
| Location requires review | `W-001010` |
| Completed with full closure records | `W-001111` |
| Completed with missing closure records | `W-001212` |
| Deterministic compliance issue | `W-001313` |
| Multi-signal high-priority case | `W-001937` |
| Enriched legacy execution case | `W-002760` |

## 5. Cost-overrun intelligence

Observed cost overrun remains the deterministic condition `final actual expenditure > sanctioned amount`. Predictive output is separately labelled **Cost Overrun Early Warning** and is never described as fraud or a confirmed overrun.

Three candidates were evaluated with work-level train/validation/test separation: Logistic Regression, Random Forest, and XGBoost. XGBoost was selected for the v2 synthetic execution-stage early warning.

### Selected model test metrics

| Metric | Value |
|---|---:|
| Positive prevalence | 0.2740 |
| ROC-AUC | 0.8009 |
| PR-AUC | 0.6768 |
| Precision | 0.5167 |
| Recall | 0.7152 |
| F1 | 0.6000 |
| Brier score | 0.1543 |
| Review threshold | 0.39 |
| Confusion matrix | `[[299, 101], [43, 108]]` |

Calibration was evaluated and recorded as `NOT_APPLIED`; no unsupported calibration claim is made. The model is marked `SYNTHETIC_HOLDOUT_SUPPORTED`, not production validated. It is secondary evidence, uses only execution-time inputs available before the final outcome, and does not expose prohibited final-cost, completion, ground-truth, duplicate-helper, or scenario-tag fields.

## 6. Lifecycle anomaly intelligence

- Three independent Isolation Forest models were trained for `PRE_SANCTION` (498 works), `EXECUTION` (1,750 works), and `COMPLETION` (2,752 works).
- Evaluation labels were loaded only by the isolated evaluation path and were not used for fitting, feature selection, serving, API output, or Review Priority.
- Synthetic Holdout Evaluation: ROC-AUC `0.5341`, PR-AUC `0.2232`, label prevalence `0.0362`.
- This weak evaluation result is reported honestly: the detector identifies unusual combinations and is not a fraud classifier.

## 7. Duplicate candidate retrieval

- Local model: `sentence-transformers/all-MiniLM-L6-v2`.
- Retrieval: normalized local embeddings with top-5 nearest neighbours; an all-pairs comparison was not used.
- Both planted synthetic candidate pairs were retrieved (`2/2`).
- Three corroborated review-candidate pairs were produced.
- Similar but non-identical neighbours are retained in the candidate space.
- Ground truth was not used for candidate generation, and a candidate is never represented as a confirmed duplicate.

## 8. Geo-tagged evidence workflow

- IA users can initiate live camera capture or separately identify uploaded-image provenance.
- Browser/device location and capture time are captured automatically; the user does not type GPS or timestamps.
- Backend runtime storage calculates SHA-256 and appends metadata under `data/runtime/site-evidence` without writing into source CSVs.
- The execution rule checks for evidence within the first three Monday–Friday working days of each reporting month. No claim is made that this prototype includes official State holiday calendars.
- Completion evidence is checked within three working days of recorded completion; monthly requirements stop after completion.
- Statuses remain lifecycle aware: Recorded, Upcoming, Due, Overdue/Requires Review, and Not Applicable.
- Missing/late evidence is an explicit deterministic review warning, not fraud and not an automatic Review Priority multiplier.
- Registered-to-capture distance is evaluated at the documented, configurable 500-metre prototype threshold. Missing registered coordinates yield “comparison unavailable” with no penalty.
- Image hashes prove stored-file integrity, not scene authenticity.
- District verification is permission checked and append-only; IA submits, District reviews, State/MoSPI monitor, and MP access is read only.

## 9. Review Priority

Geo-evidence warnings contribute exactly zero Review Priority points. The v2-only completion policy was corrected so an observed cost overrun can contribute through `OBSERVED_CONDITIONS`; this did not alter the P0 policy or artifacts.

V2 distribution:

- Low: 3,478
- Medium: 735
- High: 756
- Critical: 31
- High/Critical queue: 787
- Requires Review: 1,959

Scores remain explainable human-review priority, not wrongdoing probabilities. Evidence is capped and reduced within governed families to prevent multiplication by repeated rows.

## 10. Work-detail UI

The officer dossier provides the required nine sections in order:

1. Project Details
2. Monitoring Health
3. Anomalies & Irregularities
4. Key Risk Areas
5. Progress & Schedule
6. Geo-Tagged Progress Evidence
7. Records & Completion Readiness
8. Explanation
9. Officer Review History

The implementation includes a fixed desktop section sidebar, responsive mobile section navigation, progressive disclosures, full-width expanded analytical detail, an accessible chronological timeline, evidence-first terminology, visible focus states, icon-plus-text statuses, and technical explanations separated from the primary officer view.

The explanation button now calls the backend only after an explicit user action. Ordinary navigation makes no explanation-provider request. The deterministic fallback remains available without credentials or network access, and the frontend does not receive secrets.

## 11. Role dashboards and authoritative scope

The MP, Implementing Agency, District, State, and MoSPI dashboards were implemented with their role-specific ordered sections, deterministic morning briefs, scope-aware aggregates, data-derived comparisons, accessible text equivalents for charts/maps, and officer-oriented actions.

Backend scope is authoritative for dashboards, works, reports, explanations, geo evidence, reviews, alerts, queues, and map aggregates:

- MP: assigned constituency/MP scope
- IA: assigned implementing-agency scope
- District: state and district scope
- State: state scope
- MoSPI: national scope

All 54 synthetic implementing agencies have assigned work. Cross-scope work access returns the existing safe not-found behavior. Automated tests cover all five role scopes, and local browser checks exercised each role.

## 12. Verification results

| Check | Result |
|---|---|
| Full Python suite | **227 passed**, one third-party Starlette/httpx deprecation warning |
| Frontend tests | **11 passed, 0 failed** |
| ESLint | Passed, no errors |
| Next.js production build | Passed; seven application routes built |
| Local FastAPI health | Passed |
| Local profile/data integrity | Passed |
| Browser application console | 0 errors, 0 warnings in final dashboard and dossier smoke |
| Ordinary-navigation Groq calls | **0** |
| Deterministic explanation fallback | Passed |
| Case-review PDF | Passed; three readable pages, no secrets, `NaN`, or `None` |
| Desktop sidebar | Fixed and usable |
| Mobile layout | Verified at 500 px; no horizontal page overflow |
| Dossier cases | Normal, delay, observed overrun, duplicate, missing geo, completed-record, and multi-signal cases loaded |

The final browser smoke loaded `W-000101`, `W-000202`, `W-000505`, `W-000707`, `W-000808`, `W-001111`, and `W-001937`. The representative `W-001937` dossier reproduces a v2 Review Priority score of `74.109474` (`74.1` in officer display).

Local evidence retained for review:

- `output/screenshots/mospi-dashboard-desktop.png`
- `output/screenshots/mospi-dashboard-mobile-500.png`
- `output/screenshots/work-W-001937-desktop.png`
- `output/screenshots/work-W-001937-mobile-500.png`
- `output/pdf/MPLADS_Sentinel_V2_W-001937.pdf`

## 13. Baseline and ground-truth integrity

- `git diff 574f9ef -- Demo-data data/processed code/models` is empty.
- All 12 P0 `Demo-data` SHA-256 hashes remain unchanged.
- Baseline source tables, generated analytical artifacts, models, rules, and manifests remain reproducible and unchanged.
- `MPLADS_DATASET_PROFILE=baseline` remains available; `demo_v2` is independently loadable.
- The baseline and v2 anomaly ground-truth files remain evaluation only.
- The operational v2 loader explicitly reports `ground_truth_loaded=false`.
- No ground-truth column is exposed through model inputs, Review Priority, production repositories, APIs, or frontend types.

## 14. Key commands used

- `git status --short`, `git rev-parse --short HEAD`, `git log -5 --oneline --decorate`
- `git switch -c feature/sih-final-enhancements 574f9ef`
- `C:\SIH-PROJECT\.venv\Scripts\python.exe scripts\generate_demo_v2.py`
- `C:\SIH-PROJECT\.venv\Scripts\python.exe scripts\build_demo_v2_intelligence.py`
- `C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest`
- `npm test`, `npm run lint`, `npm run build`, `npm start`
- `C:\SIH-PROJECT\.venv\Scripts\python.exe -m uvicorn code.backend.main:app --host 127.0.0.1 --port 8000`
- `C:\SIH-PROJECT\.venv\Scripts\python.exe scripts\generate_v2_case_report.py --work-id W-001937`
- Poppler PDF rendering and visual page inspection
- Local desktop/mobile browser smoke tests and console/network inspection
- SHA-256, manifest, foreign-key, profile-isolation, and Git diff verification

## 15. Remaining limitations and production evolution

- All v2 data, coordinates, seeded images, patterns, and evaluation labels are synthetic. The metrics are not evidence of real-world performance.
- The anomaly holdout result is weak and must not be promoted as a validated risk classifier.
- The cost early-warning model is supported only on the synthetic holdout; observed deterministic expenditure remains authoritative.
- The accessible state/district “map” is an aggregate geographic comparison rather than licensed production geometry.
- The working-day calculation lacks official State holiday calendars.
- Local CSV/JSON artifacts and append-only local evidence are prototype storage, not production persistence.
- Authentication is represented by scoped prototype context, not Government SSO/RBAC.
- Production evolution requires official MPLADS/PFMS feeds, a governed warehouse/database, approved object storage, authentication/RBAC, official calendars, scheduled pipelines, persistent audit storage, a managed model registry, and a scalable vector index.

Implementation is stopped locally at the requested review boundary. No deployment activity is authorized or pending.
