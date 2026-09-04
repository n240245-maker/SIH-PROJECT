# DAY 1 REPORT — CSV Data Loader + Validation Engine

Execution date: 2026-09-01  
Project root: `C:\SIH-PROJECT`  
Controlled validation date: `AS_OF_DATE=2026-09-01`

# 1. Day 1 Goal

Day 1 implemented the approved Python bootstrap, central path/configuration handling,
strict CSV loading, schema/key/relationship/data-quality validation, isolated
evaluation-label loading, machine-readable validation reports, and automated tests.

No feature engineering, model training, duplicate embeddings, compliance engine,
RAG, Grok, FastAPI, backend API, frontend, risk fusion, or Day 2 work was implemented.

# 2. Python Environment

The project uses the user-created virtual environment and does not depend on the
system-default Python 3.14 or the private Codex runtime.

- Version: Python 3.12.10
- Executable: `C:\SIH-PROJECT\.venv\Scripts\python.exe`
- pip: 25.0.1 from `C:\SIH-PROJECT\.venv\Lib\site-packages\pip`
- Base installation supplied by the user:
  `C:\Users\harsh\AppData\Local\Python\pythoncore-3.12-64\python.exe`

Verification commands and results:

```text
C:\SIH-PROJECT\.venv\Scripts\python.exe --version
Python 3.12.10

C:\SIH-PROJECT\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
C:\SIH-PROJECT\.venv\Scripts\python.exe

C:\SIH-PROJECT\.venv\Scripts\python.exe -m pip --version
pip 25.0.1 ... (python 3.12)
```

# 3. Dependencies Added

Only the approved Day-1 dependencies were declared in `pyproject.toml` and installed
with `C:\SIH-PROJECT\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.

Direct resolved packages:

| Use | Package | Resolved version |
|---|---|---:|
| Runtime | numpy | 2.5.2 |
| Runtime | pandas | 2.3.3 |
| Runtime | pandera | 0.26.1 |
| Runtime | pydantic | 2.13.5 |
| Runtime | pydantic-settings | 2.15.0 |
| Runtime | python-dateutil | 2.9.0.post0 |
| Development | pytest | 8.4.2 |

Resolved transitive packages were: annotated-types 0.8.0, colorama 0.4.6,
iniconfig 2.3.0, mypy_extensions 1.1.0, packaging 26.3, pluggy 1.6.0,
pydantic_core 2.46.5, Pygments 2.21.0, python-dotenv 1.2.3, pytz
2026.3.post1, six 1.17.0, typeguard 4.6.0, typing_extensions 4.16.0,
typing-inspect 0.9.0, typing-inspection 0.4.4, and tzdata 2026.3.

No future ML, RAG, backend, Grok/xAI, or frontend dependency was installed.

# 4. Files Created

Created source/configuration files:

- `C:\SIH-PROJECT\pyproject.toml`
- `C:\SIH-PROJECT\code\intelligence\__init__.py`
- `C:\SIH-PROJECT\code\intelligence\data\__init__.py`
- `C:\SIH-PROJECT\code\intelligence\data\config.py`
- `C:\SIH-PROJECT\code\intelligence\data\paths.py`
- `C:\SIH-PROJECT\code\intelligence\data\schemas.py`
- `C:\SIH-PROJECT\code\intelligence\data\loader.py`
- `C:\SIH-PROJECT\code\intelligence\data\validation.py`
- `C:\SIH-PROJECT\code\intelligence\data\reports.py`
- `C:\SIH-PROJECT\code\tests\conftest.py`
- `C:\SIH-PROJECT\code\tests\test_loader.py`
- `C:\SIH-PROJECT\code\tests\test_validation.py`
- `C:\SIH-PROJECT\code\tests\test_outputs_and_integrity.py`
- `C:\SIH-PROJECT\DAY_1_REPORT.md`

Generated output files:

- `C:\SIH-PROJECT\data\processed\validation_summary.json`
- `C:\SIH-PROJECT\data\processed\validation_issues.csv`

Modified root documentation/configuration:

- `C:\SIH-PROJECT\README.md` — added Day-1 status and commands.
- `C:\SIH-PROJECT\.gitignore` — added `*.egg-info/` for editable-install metadata.

The editable installation also generated ignored packaging metadata under
`C:\SIH-PROJECT\code\mplads_risk_intelligence.egg-info\`.

# 5. Loader Design

`ProjectPaths` derives the repository root and centrally exposes `PROJECT_ROOT`,
`DEMO_DATA_DIR`, `PROCESSED_DATA_DIR`, `GUIDELINES_DIR`, and `MODELS_DIR`.
`Day1Settings` reads `AS_OF_DATE` from the environment or an optional uncommitted
root `.env`; the controlled prototype default is explicitly 2026-09-01 and does
not use the current clock.

`load_operational_data()` loads exactly six independent DataFrames:

| Bundle field | Source | Rows |
|---|---|---:|
| mp | 01_mp_master.csv | 36 |
| entities | 02_agencies_vendors.csv | 108 |
| works | 03_works.csv | 3,000 |
| payments | 04_payments.csv | 9,727 |
| progress | 05_progress.csv | 14,902 |
| assets | 06_assets_compliance.csv | 1,929 |

Payments and progress remain separate one-to-many histories. No operational API
creates a giant merged table. A diagnostic-only algebraic calculation confirms:

- Works: 3,000 rows
- Works left-joined to payments: 10,011 rows
- Works left-joined to progress: 15,172 rows
- Naive works/payments/progress expansion: 53,640 rows, or 17.88x

Later feature engineering must aggregate histories into one row per work.
Official supplemental CSVs and metadata/control CSVs have separate helper loaders
and are not automatically merged into the operational data.

# 6. Ground-Truth Isolation Design

`07_anomaly_ground_truth.csv` is absent from `OperationalDataBundle` and is never
read by `load_operational_data()`. It requires the explicit
`load_evaluation_ground_truth()` call, whose documentation marks it **EVALUATION
ONLY**. Its integrity validator is separate from operational validation.

Tests prove that the operational bundle exposes only `mp`, `entities`, `works`,
`payments`, `progress`, and `assets`; that operational-loader source does not
reference ground truth; and that the evaluation file is available only through
the explicit evaluation loader. No feature matrix exists, so no ground-truth
column is used as a production/model feature.

# 7. Schema Validation

Exact, ordered Pandera-backed schemas were implemented for all six operational
files. The loader reads raw fields first, rejects missing/unexpected/reordered
columns, and explicitly parses strings/categories, numeric values, `true`/`false`
booleans, and `%Y-%m-%d` dates while preserving allowed null dates.

Missing files, missing or unexpected columns, malformed dates, invalid booleans,
non-numeric values, non-integral integer values, and null required fields produce
clear `DataLoadError` failures. No columns are invented, renamed, or silently fixed.
All six current schemas passed.

# 8. Key / Relationship Validation

All required primary keys passed non-nullness and uniqueness checks:
`mp.mp_id`, `entities.entity_id`, `works.work_id`, `payments.payment_id`,
`progress.progress_id`, `assets.asset_id`, and `assets.work_id`.

Relationship results:

| Relationship | Matched/non-null | Null | Invalid/unmatched/type | Result |
|---|---:|---:|---:|---|
| works.mp_id → mp.mp_id | 3,000/3,000 | 0 | 0 | PASS |
| works.implementing_agency_id → agency entity | 2,730/2,730 | 270 allowed | 0 | PASS |
| payments.work_id → works.work_id | 9,727/9,727 | 0 | 0 | PASS |
| payments.vendor_id → vendor entity | 9,727/9,727 | 0 | 0 | PASS |
| payments.authorized_by_agency_id → agency entity | 9,727/9,727 | 0 | 0 | PASS |
| progress.work_id → works.work_id | 14,902/14,902 | 0 | 0 | PASS |
| progress.reported_by_agency_id → agency entity | 14,902/14,902 | 0 | 0 | PASS |
| assets.work_id → works.work_id | 1,929/1,929 | 0 | 0 | PASS |

Every non-null reference matched (100%), and no entity-type mismatch was found.

# 9. Chronology / Quality Validation

Day-1 validation checks required physical-progress and coordinate ranges, negative
monetary values, important work/payment/progress/closure chronology, actual events
after `AS_OF_DATE`, progress sequences in stable `work_id` + `report_date` +
`progress_id` order, same-day progress duplicates, PFMS duplication, zero released
payments, payment totals and stable-order cumulative totals, and transparent
status/execution inconsistencies.

`financial_progress_pct > 100` is deliberately a warning/risk signal rather than
a parser failure. Planned future expected-completion dates are not treated as
invalid. All warning messages are factual review signals; none alleges wrongdoing.

# 10. Validation Findings

Final severity totals:

- ERROR: 0
- WARNING: 13,332
- INFO: 0

Issue-code counts:

| Issue code | Count |
|---|---:|
| FUTURE_ACTUAL_EVENT | 7,987 |
| FINANCIAL_PROGRESS_OVER_100 | 4,292 |
| PAYMENT_AUTH_BEFORE_REQUEST | 718 |
| PHYSICAL_PROGRESS_DECREASE | 295 |
| DUPLICATE_WORK_REPORT_DATE | 13 |
| PROGRESS_BEFORE_ACTUAL_START | 12 |
| STATUS_EXECUTION_INCONSISTENCY | 10 |
| ZERO_RELEASED_PAYMENT | 4 |
| DUPLICATE_PFMS_REFERENCE | 1 |

The expected Day-0.5 observations were reproduced from data, not hard-coded in
production logic:

- 718 payment authorizations precede requests.
- 12 progress reports precede actual start across 5 works.
- 4,292 progress rows have financial progress above 100.
- 295 physical-progress decreases occur across 220 works.
- 13 same-work/same-report-date duplicate extras exist.
- One duplicate PFMS-reference extra exists.
- Four released payments have zero value.
- Of 24 works marked `Sanctioned - Not Started`, 9 have non-zero physical
  progress, 10 have expenditure, 10 have payment rows, and 10 distinct works have
  at least one of these execution signals.

Payment sums equal `works.current_expenditure_inr` for every payment-bearing work.
After the Day 1.1 sequence audit, the evidence-supported deterministic order finds
zero reported cumulative-payment discrepancies. See the audit section below for
why the original order produced 97 warnings.

# 11. Output Artifacts

The validator generated only these Day-1 reports under
`C:\SIH-PROJECT\data\processed`:

- `validation_summary.json` — 6,252 bytes; configuration, rows, schemas, keys,
  relationships, quality summaries, and issue counts.
- `validation_issues.csv` — 3,862,263 bytes; 13,332 factual issue records plus header.

No generated validation artifact was written into `Demo-data`.

Run from the project root:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.data.validation
```

# 12. Tests

The focused suite covers loading, fixed row counts, exact schemas, date parsing,
key integrity, all required relationships, progress relationship integrity,
ground-truth isolation, separate payment/progress DataFrames, absence of a giant
merged production table, diagnostic join cardinality, output location, known
findings, and all source hashes.

Command:

```powershell
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final Day 1.1 result: **16 passed in 2.02 seconds** on Python 3.12.10.

# 13. Source Integrity Verification

SHA-256 hashes were recorded before implementation and checked again both directly
and by pytest after validation. All 12 CSV files under `C:\SIH-PROJECT\Demo-data`
exactly match their baseline hashes. No source CSV was modified, renamed, moved,
deleted, or overwritten.

# 14. Known Limitations

- The operational prototype tables are synthetic and do not establish production
  readiness or model performance.
- The two official supplemental MP CSVs still lack a safe identity crosswalk to
  the synthetic MP master and therefore remain separate.
- The 7,987 future actual-event warnings reflect the explicit 2026-09-01 cutoff
  and require source/business interpretation; planned future completion dates are
  intentionally excluded from this warning.
- Validation signals are not proof of fraud and require authorized human review.
- No one-row-per-work project feature table exists yet.
- No feature engineering, ML, duplicate detection, compliance logic, RAG, API,
  frontend, or integration layer exists yet.

# Day 1.1 Payment Sequence Audit

The original cumulative check sorted each work by release date, authorization
date, request date, and payment ID. Its 97 warnings affected 97 payment rows in
44 works (272 total payment rows across those works). All 97 warning rows were in
47 same-day release groups, and every affected work contained a same-day release
tie. Across the affected works' full histories, 16 works also had tied
authorization dates and 13 had tied request dates. Within the 47 groups actually
reordered, 10 groups had an authorization tie and 2 had a request tie.

The release-date ties exposed the real cause: authorization and request dates do
not reliably express installment order. In the source-defined stage sequence,
authorization dates move backward 80 times and request dates move backward 247
times across the full payment table. Using them to break a release-date tie can
therefore place a later installment before an earlier one.

The dataset provides stronger and mutually corroborating sequence evidence:

- Original CSV row order reproduces every reported cumulative value: 0 mismatches.
- Every one of 9,727 rows has a parseable natural `Stage N` number.
- Stage numbers are unique and contiguous from 1 through N within every
  payment-bearing work.
- The natural stage number exactly equals both the payment-ID suffix and invoice
  suffix on all 9,727 rows.
- Release dates never decrease in natural stage/source order.
- Natural stage order and invoice-suffix order each reproduce all cumulative
  values. Plain string sorting by `payment_stage` is not valid: it creates 72
  mismatches in 8 ten-stage works because `Stage 10` sorts before `Stage 2`.

The recommended canonical order for this prototype and future feature work is:

1. `work_id`
2. `payment_release_date`
3. natural numeric value parsed from `payment_stage`
4. `payment_id` as deterministic final tie-breaker

This choice is based on explicit stage semantics corroborated by identifiers,
invoice sequence, source order, and monotonic release dates—not merely on making
warnings disappear. Source row order and invoice/payment-ID suffixes are useful
corroboration but should not be the primary semantic rule. `validation.py` was
updated accordingly. The current cumulative mismatch/ambiguity count is **0**;
the overall warning total fell only by the original 97 rows, from 13,429 to 13,332.

Permanent guardrails were also added to `AGENTS.md`: validation row counts are not
risk scores; repeated warnings must be aggregated at work level rather than
automatically multiplying risk; `FUTURE_ACTUAL_EVENT` may be a synthetic
temporal-context artifact; and later risk fusion must explicitly decide whether
data-quality signals contribute. No risk fusion was implemented.

The current asset table has unique `asset_id` and `work_id` and one row per
completed work. This is documented as a prototype-data property, not a universal
MPLADS rule; future project-profile code must still aggregate multiple asset rows
per work if real data contains them. The Day-1 schema was not changed.

# 15. Recommended Day 2

**Day 2 — Unified Project Profile + Core Feature Engineering**

Day 2 has not been started. Explicit approval is required before proceeding.
