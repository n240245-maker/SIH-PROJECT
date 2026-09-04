# DAY 2 REPORT — Unified Project Profile + Core Feature Engineering

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled feature snapshot: `AS_OF_DATE=2026-09-01`

# 1. Day 2 Goal

Day 2 implemented a reusable unified project profile, leakage-aware as-of views,
independent work-level lifecycle aggregations, a deterministic one-row-per-work
feature snapshot, a complete feature catalog, feature-quality checks, and focused
tests.

No model training, anomaly scoring, supervised target, duplicate similarity,
compliance rules, RAG, Grok, FastAPI, frontend, or risk fusion was implemented.

# 2. Files Created / Modified

Created:

- `code/intelligence/features/__init__.py`
- `code/intelligence/features/aggregations.py`
- `code/intelligence/features/builder.py`
- `code/intelligence/features/catalog.py`
- `code/intelligence/features/profile.py`
- `code/tests/test_features.py`
- `data/processed/project_features.csv`
- `data/processed/feature_catalog.json`
- `DAY_2_REPORT.md`

Modified:

- `code/tests/conftest.py` — shared Day-2 snapshot fixtures.
- `AGENTS.md` — runtime-snapshot/training guardrail and leakage blacklist.
- `README.md` — Day-2 status and builder command.

Removed:

- `code/intelligence/features/.gitkeep` — replaced by the implemented package.

No dependency was added and no Day-1 validation-report semantics were changed.

# 3. Unified Project Profile Design

`build_project_profile(work_id, bundle, as_of_date, feature_table=...)` resolves
exactly one work, its MP, and its implementing agency when one exists. It exposes:

- safe work context, with source-current fields explicitly named;
- MP context from the validated operational MP master;
- implementing-agency context from the entity master;
- only released payments whose release date is visible by the snapshot;
- only progress reports visible by the snapshot;
- completed asset rows with future closure-event dates masked; and
- the exact corresponding derived feature row.

The API accepts only `OperationalDataBundle`; it neither loads ground truth nor
the official supplemental files. It is an in-memory representation and does not
write 3,000 profile JSON files.

# 4. As-Of Leakage Policy

The controlled snapshot is 2026-09-01.

- Payments require `payment_status == Released` and
  `payment_release_date <= AS_OF_DATE`.
- Progress requires `report_date <= AS_OF_DATE`.
- Completion and each closure flag require their own event date to be on or before
  the snapshot.
- Actual start is exposed only when `actual_start_date <= AS_OF_DATE`.
- Sanction-derived values are exposed only when sanction date is visible.
- Expected start/completion dates remain usable plan fields even when future.
- Final expenditure is exposed only for an asset row whose completion-marked date
  is visible, a conservative finalization rule.

The source lacks ingestion timestamps. Consequently, `current_status`, current
physical progress, and current expenditure are retained only under
`source_current_*` names for context/reconciliation and are not model eligible.

# 5. Lifecycle Stage Logic

Lifecycle is deterministic, not predicted:

1. `PRE_SANCTION` when the work is rejected or no sanctioned state is visible by
   the snapshot.
2. `COMPLETION` when sanctioned and at least one completion record is visible by
   the snapshot.
3. `EXECUTION` for other sanctioned-as-of works, including sanctioned/not-started.

Current counts are 270 `PRE_SANCTION`, 801 `EXECUTION`, and 1,929 `COMPLETION`.
The separate `is_rejected` context flag preserves the rejection distinction.

# 6. Feature Groups

The output contains 76 columns in these catalog categories:

| Category | Columns |
|---|---:|
| identifier | 3 |
| context | 9 |
| lifecycle | 2 |
| financial | 10 |
| payment | 13 |
| progress | 13 |
| schedule | 10 |
| completion | 11 |
| reconciliation | 5 |

The initial Day-2 catalog marked 49 deterministic numeric/boolean fields as broadly
model eligible. The Day-2.1 audit below separates broader technical usability from
current generic-anomaly eligibility and documents the refined counts.

# 7. Payment Aggregation

Payments are filtered and aggregated independently before joining the work spine.
The canonical Day-1.1 ordering is:

`work_id`, `payment_release_date`, natural numeric `payment_stage`, `payment_id`.

Features include counts and totals, vendor count, largest/mean payment, largest
share, first/latest release dates, days since payment, final-payment evidence,
zero-value released-payment count, and vendor concentration.

Vendor HHI is:

`sum((vendor released amount / total released amount)^2)`

HHI and payment-share features are null when total released amount is not positive.
As-of released-payment total is the preferred expenditure measure.

# 8. Progress Aggregation

Progress is independently filtered and sorted by `work_id`, `report_date`, and
`progress_id`. Features include report counts, first/latest dates and observations,
financial/expected gaps to physical progress, recency, decreases, maximum drop,
same-day extras, and observed velocity.

Velocity is:

`(latest physical progress - first physical progress) / elapsed days * 30`

It is null unless at least two chronologically distinct report dates exist. No
interpolation or invented progress is used.

# 9. Schedule Features

Static plan features include amount ratios, days from recommendation to sanction,
planned duration, and days from sanction to expected start. Snapshot features
include visible actual-start availability/age, signed days to expected completion,
overdue days for works not completed as of the snapshot, and schedule elapsed ratio.

Schedule elapsed ratio is elapsed days since expected start, floored at zero,
divided by positive planned duration. It may exceed one. No threshold-based
`delayed` label or delay prediction was created.

# 10. Completion / Asset Features

Asset records are always grouped by `work_id`; the implementation does not rely
on the current one-row-per-work source shape. A regression test duplicates an
asset record and confirms that aggregation still returns one work row.

Features include visible asset count, completion date/flag, completion-marked,
UC, handover, public-use and audit flags, conservative final expenditure, actual
duration, and signed completion difference from the expected date. A future event
never sets its corresponding as-of flag.

# 11. Reconciliation Features

The source-current fields are retained as:

- `source_current_status`
- `source_current_physical_progress_pct`
- `source_current_expenditure_inr`

Audit differences compare source-current expenditure with released as-of spend,
and source-current physical progress with the latest visible progress observation.
All five reconciliation-category fields are marked non-model-eligible because the
source snapshot may represent later/final state.

# 12. Leakage Blacklist

The feature code never loads `07_anomaly_ground_truth.csv`. No ground-truth label,
`injected_anomaly_*`, `expected_risk_*`, or ground-truth-derived value appears in
the table or catalog.

`duplicate_group_reference` is not read into any feature formula and is absent
from the output. Raw one-to-many identifiers such as `payment_id`, `progress_id`,
`asset_id`, and `vendor_id` are also absent. Operational identifiers such as
`work_id`, `mp_id`, and `implementing_agency_id` are cataloged as non-model
identifiers rather than risk evidence.

No validation warning count was converted into a risk score or feature.

# 13. Feature Catalog

`data/processed/feature_catalog.json` contains exactly one definition for each of
the 76 output columns, in feature-table order. Every definition includes:

- name
- category
- description
- formula or source
- data type
- `model_eligible`
- `generic_anomaly_eligible`
- generic-anomaly selection notes
- leakage notes

The artifact also states permanently that this is a runtime/current as-of snapshot
and not automatically valid for supervised prediction training.

# 14. Generated Feature Table

`data/processed/project_features.csv` contains exactly **3,000 rows x 76 columns**.
There are 3,000 unique, non-null `work_id` values, and the work-ID set exactly
matches the operational work table. The file size is 1,891,846 bytes.

Every one-to-many source was aggregated independently before a validated one-to-one
join. No works/payments/progress history expansion was constructed.

Run from the project root:

```powershell
$env:AS_OF_DATE = '2026-09-01'
.\.venv\Scripts\python.exe -m intelligence.features.builder
```

# 15. As-Of Diagnostics

| Diagnostic | Result |
|---|---:|
| Released payment rows included | 9,672 |
| Released payment value included | INR 4,984,010,000 |
| Future payment releases excluded | 55 |
| Future payment value excluded | INR 3,714,000 |
| Progress rows included | 14,902 |
| Future progress rows excluded | 0 |
| Works with zero visible progress reports | 270 |
| Works completed as of snapshot | 1,929 |

Future completion/closure events excluded from their flags:

| Event | Excluded future rows | As-of true flags |
|---|---:|---:|
| completion | 0 | 1,929 |
| completion marked | 1,597 | 332 |
| utilization certificate | 1,890 | 0 |
| handover | 1,828 | 101 |
| public use | 1,874 | 55 |
| audit | 647 | 0 |

Four future actual-start dates were also excluded. The 547 future planned
completion dates remain available as plans and are not treated as future actual
events.

# 16. Tests

The complete Day-1 plus Day-2 suite covers loading and source hashes, validation,
one-row cardinality, leakage blacklists, independent aggregates, payment/progress
as-of behavior, ratio safety, lifecycle rules, completion flags, multi-asset
aggregation, catalog coverage, required artifact location, and profiles for
pre-sanction, execution, and completion examples.

Command:

```powershell
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final Day-2.1 result: **36 passed in 3.91 seconds** on Python 3.12.10.

# 17. Source Integrity

The full regression suite rechecked every SHA-256 baseline. All 12 CSV files under
`Demo-data` remain byte-for-byte unchanged. No source file was modified, renamed,
moved, deleted, or overwritten. Generated files exist only under `data/processed`.

# 18. Known Limitations

- The operational data is synthetic and lacks ingestion/snapshot timestamps.
- `project_features.csv` is a single runtime as-of snapshot, not a leakage-safe
  supervised training dataset for delay or cost-overrun prediction.
- Historical training would require multiple time-aware snapshots plus carefully
  timed outcomes; no labels were created on Day 2.
- Rejection has no dated event field, so `is_rejected` is routing/context only.
- Current final-expenditure aggregation assumes additive per-asset values; real
  multi-asset source semantics must be verified before production use.
- The two official MP supplemental files remain separate because no safe identity
  crosswalk exists.
- No anomaly model, peer benchmark, score, compliance rule, or risk fusion exists.

# Day 2.1 Model Eligibility Audit

This label-free audit examined all 54 numeric/boolean columns in the 3,000-row
runtime snapshot. It did not load ground truth, change feature formulas, or alter
any `project_features.csv` value. The file's SHA-256 remained
`760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148`
before and after the audit.

## Eligibility interpretation

The initial catalog had 49 `model_eligible=true` fields. Day 2.1 adds
`generic_anomaly_eligible` to every one of the 76 catalog entries:

- `model_eligible`: technically usable for some future modelling or intelligence
  task when its semantics and lifecycle stage are appropriate.
- `generic_anomaly_eligible`: admitted to the current audited Day-3 generic
  anomaly candidate pool.

Four current zero-variance fields were removed from broader model eligibility,
leaving 45 broadly model-eligible fields. After lifecycle, synthetic-artifact,
compliance, redundancy, and near-zero-variance exclusions, **32 fields remain in
the current generic-anomaly candidate pool**. These are candidates only, not an
automatic model matrix or a claim of optimality.

Current generic exclusions added by the audit are:

- Payment/concentration: `unique_vendor_count_as_of`, `vendor_hhi_as_of`,
  `final_payment_count_as_of`, `has_final_payment_as_of`, and
  `zero_value_released_payment_count_as_of`.
- Progress quality: `days_since_last_progress_report_as_of` and
  `same_day_progress_extra_count_as_of`.
- Completion/routing/compliance: `asset_record_count_as_of`,
  `is_completed_as_of`, `completion_marked_as_of`, `uc_recorded_as_of`,
  `handover_recorded_as_of`, `public_use_recorded_as_of`,
  `audit_recorded_as_of`, `final_expenditure_inr_as_of`,
  `actual_duration_days`, and `completion_delay_days`.

`final_payment_count_as_of` and `has_final_payment_as_of` exactly equal completion
state in this synthetic snapshot. `asset_record_count_as_of` is likewise exactly
0 for non-completed works and 1 for completed works. They are routing/context
signals, not inputs for distinguishing lifecycle stages inside one global model.

## Variance and missingness findings

Near-zero variance is defined as a non-constant feature whose dominant non-null
value represents at least 99% of non-null observations.

Zero-variance features:

- `vendor_hhi_as_of`: 1.0 for all 2,706 non-null rows.
- `days_since_last_progress_report_as_of`: 1 day for all 2,730 non-null rows.
- `uc_recorded_as_of`: false for all 3,000 rows.
- `audit_recorded_as_of`: false for all 3,000 rows.
- `source_vs_asof_physical_progress_difference_pct`: 0 for all 2,730 non-null rows.

Near-zero-variance features:

- `zero_value_released_payment_count_as_of`: zero for 99.9667% of rows.
- `same_day_progress_extra_count_as_of`: zero for 99.9333% of rows.
- `source_vs_asof_expenditure_difference_inr`: zero for 99.3333% of rows;
  it was already reconciliation-only.

No audited numeric/boolean feature had at least 90% missingness.
`final_expenditure_inr_as_of` was highest at 88.9333% null because the conservative
availability rule exposes it only for 332 completion-marked works.

## Closure-flag audit

All flags have 3,000 non-null rows:

| Feature | True | False | Unique | True prevalence |
|---|---:|---:|---:|---:|
| completion_marked_as_of | 332 | 2,668 | 2 | 11.0667% |
| uc_recorded_as_of | 0 | 3,000 | 1 | 0.0000% |
| handover_recorded_as_of | 101 | 2,899 | 2 | 3.3667% |
| public_use_recorded_as_of | 55 | 2,945 | 2 | 1.8333% |
| audit_recorded_as_of | 0 | 3,000 | 1 | 0.0000% |

These are retained for completion evidence and later deterministic compliance
intelligence but excluded from the current generic anomaly pool because they are
constant or dominated by the synthetic future-event cutoff.

## Completion-date synthetic artifact

All 1,929 synthetic completion rows use 2026-08-31. Although
`actual_duration_days` and `completion_delay_days` still vary through their start
and planned dates, the common completion date makes their current distributions
generator-dependent. Their formulas remain useful for dashboards/evidence, but
both are excluded from the current generic anomaly pool.

`final_expenditure_inr_as_of` remains in the table and is broadly calculable, but
is excluded from the generic pool because it is completion-specific, 88.9333%
missing at this snapshot, and real multi-asset amount semantics are not verified.

## Payment-concentration audit

`unique_vendor_count_as_of` is 0 for 293 works and 1 for 2,707 works; no work has
multiple visible vendors. `vendor_hhi_as_of` has 2,706 non-null values and 294
nulls, with minimum, maximum, and mean all equal to 1.0 and standard deviation 0.
It therefore provides no current concentration variation. Both features remain
available for future real multi-vendor data but are excluded from the current
generic anomaly pool.

## Lifecycle routing policy

Future anomaly selection must route by lifecycle stage first. Pre-sanction inputs
must use pre-sanction information only; execution selection may use visible
payment/progress/schedule evidence; completion selection may use dated
completion-specific evidence. No model may blindly select every true eligibility
flag, and a feature meaningful in one stage may be constant or meaningless in
another. This rule is now permanent in `AGENTS.md`.

The machine-readable audit is
`data/processed/feature_quality_profile.json`. It contains non-null counts, null
percentages, unique counts, extrema, means, standard deviations, dominant-value
prevalence, and zero/near-zero-variance flags for all 54 audited fields.

# 19. Recommended Day 3

**Day 3 — Core Anomaly & Peer-Benchmark Intelligence**

Day 3 has not been started. Explicit approval is required before proceeding.
