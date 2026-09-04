# DAY 3 REPORT — Core Anomaly + Robust Peer-Benchmark Intelligence

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled feature snapshot: `AS_OF_DATE=2026-09-01`

# 1. Day 3 Goal

Day 3 implemented only lifecycle-aware robust peer benchmarking, label-free
stage-specific feature selection, three independent lifecycle Isolation Forest
detectors, within-stage rankings, transparent statistical evidence, model registry
artifacts, an evaluation-only synthetic-label diagnostic, and regression tests.

An anomaly means a statistically unusual pattern relative to comparable records.
It is not evidence of fraud, guilt, corruption, or non-compliance. Day 3 did not
create an automated verdict, a risk class, a probability, a fused risk score, or
an anomaly cutoff.

No XGBoost, Random Forest, delay/overrun supervised model, SHAP, duplicate semantic
detection, compliance engine, RAG, Grok, FastAPI, frontend, workflow, automated
self-learning, or Day 4 work was implemented.

# 2. Dependencies Added

Only the two approved Day-3 direct dependencies were added to `pyproject.toml` and
installed into `C:\SIH-PROJECT\.venv` with Python 3.12.10:

| Direct dependency | Declared constraint | Resolved version |
|---|---|---:|
| scikit-learn | `>=1.5,<2` | 1.9.0 |
| scipy | `>=1.13,<2` | 1.18.1 |

The installation also resolved scikit-learn's required transitive packages:
joblib 1.6.0, threadpoolctl 3.6.0, narwhals 2.25.0, and cloudpickle 3.1.2.
No future ML, embedding, RAG, backend, Grok/xAI, or frontend dependency was added.

# 3. Files Created / Modified

Created source and tests:

- `code/intelligence/anomaly/__init__.py`
- `code/intelligence/anomaly/feature_selection.py`
- `code/intelligence/anomaly/peer_benchmark.py`
- `code/intelligence/anomaly/isolation.py`
- `code/intelligence/anomaly/scoring.py`
- `code/intelligence/anomaly/evaluation.py`
- `code/intelligence/anomaly/runner.py`
- `code/tests/test_anomaly.py`
- `DAY_3_REPORT.md`

Created production artifacts:

- `data/processed/anomaly_feature_sets.json`
- `data/processed/peer_benchmark_evidence.csv`
- `data/processed/peer_benchmark_summary.csv`
- `data/processed/anomaly_scores.csv`
- `data/processed/anomaly_evidence.csv`
- `data/processed/anomaly_summary.json`
- `code/models/anomaly/isolation_forest_pre_sanction.joblib`
- `code/models/anomaly/isolation_forest_execution.joblib`
- `code/models/anomaly/isolation_forest_completion.joblib`
- `code/models/anomaly/anomaly_model_metadata.json`

Created isolated evaluation-only artifacts:

- `data/processed/evaluation/anomaly_ground_truth_metrics.json`
- `data/processed/evaluation/anomaly_ground_truth_scored.csv`

Modified `pyproject.toml`, `AGENTS.md`, and `README.md`. The empty anomaly
`.gitkeep` was removed after the package was implemented. No source CSV or Day-2
feature value was modified.

# 4. Lifecycle Routing

The existing deterministic `lifecycle_stage` was verified and used before any
feature selection or model fitting:

| Lifecycle | Works | Model |
|---|---:|---|
| PRE_SANCTION | 270 | independent pre-sanction Isolation Forest |
| EXECUTION | 801 | independent execution Isolation Forest |
| COMPLETION | 1,929 | independent completion Isolation Forest |
| **Total** | **3,000** | **3 models; no global model** |

Every stage receives its own selected columns, median imputer, fitted detector,
raw scores, unusualness orientation, percentile, and rank. `lifecycle_stage`
itself is routing context and never a model feature.

# 5. Stage-Specific Feature Sets

Selection starts only from the 32 catalog entries where
`generic_anomaly_eligible=true`. Ground truth is not consulted.

## PRE_SANCTION — 3 features

- `recommended_amount_inr`
- `technical_estimate_amount_inr`
- `estimate_to_recommended_ratio`

## EXECUTION — 31 features

- `recommended_amount_inr`
- `technical_estimate_amount_inr`
- `sanctioned_amount_inr`
- `estimate_to_recommended_ratio`
- `sanction_to_recommended_ratio`
- `sanction_to_estimate_ratio`
- `days_recommendation_to_sanction`
- `planned_duration_days`
- `days_sanction_to_expected_start`
- `released_payment_count_as_of`
- `released_payment_total_inr_as_of`
- `largest_payment_inr_as_of`
- `mean_payment_inr_as_of`
- `largest_payment_share_as_of`
- `days_since_last_payment_as_of`
- `expenditure_to_sanction_pct_as_of`
- `financial_overrun_amount_inr_as_of`
- `financial_overrun_pct_as_of`
- `progress_report_count_as_of`
- `latest_physical_progress_pct_as_of`
- `latest_financial_progress_pct_as_of`
- `latest_expected_progress_pct_as_of`
- `financial_minus_physical_gap_pct_as_of`
- `expected_minus_physical_gap_pct_as_of`
- `physical_progress_decrease_count_as_of`
- `max_physical_progress_drop_pct_as_of`
- `physical_progress_velocity_pct_per_30d`
- `days_since_actual_start_as_of`
- `days_to_expected_completion_as_of`
- `overdue_days_as_of`
- `schedule_elapsed_ratio_as_of`

## COMPLETION — 29 features

Completion uses the execution list except
`latest_physical_progress_pct_as_of`, `actual_start_available_as_of`, and
`overdue_days_as_of`, which fail completion-stage distribution/applicability
checks. No synthetic completion-date artifact, closure-routing flag,
reconciliation field, or compliance-only field is admitted.

# 6. Feature Exclusions

The transparent rules are: exclude when structurally inapplicable, more than 50%
missing within a stage, zero variance within a stage, or near-zero variance where
one non-null value represents at least 99% of stage observations.

## PRE_SANCTION

Twenty-nine generic candidates are structurally inapplicable because they require
sanction, payment, execution-progress, or execution-schedule information:

- Sanction/plan: `sanctioned_amount_inr`, `sanction_to_recommended_ratio`,
  `sanction_to_estimate_ratio`, `days_recommendation_to_sanction`,
  `planned_duration_days`, `days_sanction_to_expected_start`.
- Payment/expenditure: `released_payment_count_as_of`,
  `released_payment_total_inr_as_of`, `largest_payment_inr_as_of`,
  `mean_payment_inr_as_of`, `largest_payment_share_as_of`,
  `days_since_last_payment_as_of`, `expenditure_to_sanction_pct_as_of`,
  `financial_overrun_amount_inr_as_of`, `financial_overrun_pct_as_of`.
- Progress: `progress_report_count_as_of`,
  `latest_physical_progress_pct_as_of`, `latest_financial_progress_pct_as_of`,
  `latest_expected_progress_pct_as_of`,
  `financial_minus_physical_gap_pct_as_of`,
  `expected_minus_physical_gap_pct_as_of`,
  `physical_progress_decrease_count_as_of`,
  `max_physical_progress_drop_pct_as_of`,
  `physical_progress_velocity_pct_per_30d`.
- Execution schedule: `actual_start_available_as_of`,
  `days_since_actual_start_as_of`, `days_to_expected_completion_as_of`,
  `overdue_days_as_of`, `schedule_elapsed_ratio_as_of`.

## EXECUTION

`actual_start_available_as_of` was excluded as near-zero variance: its dominant
value accounts for approximately 99.5% of execution rows. The remaining 31
candidates passed stage checks.

## COMPLETION

- `latest_physical_progress_pct_as_of`: zero variance; every completion-stage
  value is 100 in this snapshot.
- `actual_start_available_as_of`: zero variance; every completion-stage value is
  true.
- `overdue_days_as_of`: 100% missing because the feature is intentionally defined
  for works not completed as of the snapshot.

All exclusion records, distribution statistics, selected columns, and exact
reason codes are stored in `anomaly_feature_sets.json`.

# 7. Peer Cohort Design

Peer benchmarking is a detector separate from Isolation Forest. For each metric
and work, it uses the most specific cohort with at least 20 non-null metric
observations:

1. lifecycle + state + sector + sub-sector
2. lifecycle + state + sector
3. lifecycle + sector + sub-sector
4. lifecycle + sector
5. lifecycle

The minimum of 20 is a statistical engineering choice, not an MPLADS rule. Every
current evidence row found an eligible group by Level 4; Level 5 was available but
was not required. Actual evidence-row routing was:

| Selected level | Evidence rows |
|---|---:|
| Level 1 | 378 |
| Level 2 | 39,204 |
| Level 3 | 9,921 |
| Level 4 | 2,049 |

Statistics include the focal work in its cohort. Both the chosen level and the
non-null metric peer count are retained on every evidence row.

# 8. Robust Statistics

For each work/metric cohort, the engine calculates median, MAD, Q1, Q3, IQR, P10,
and P90. When `MAD > 0`, signed deviation is:

`0.6745 * (observed - median) / MAD`

When MAD is zero but IQR is positive, the safe fallback is:

`(observed - median) / (IQR / 1.349)`

When both MAD and IQR are zero, no standardized deviation is emitted and the
constant peer distribution is not treated as an outlier. Actual method counts:

| Method | Rows |
|---|---:|
| Modified z using MAD | 42,408 |
| Standardized IQR fallback | 1,452 |
| Constant peer distribution; no score | 7,620 |
| Observed/peer value missing; no score | 72 |

For statistical evidence only, absolute deviation at least 3.5 is marked
`STATISTICAL_PEER_OUTLIER` through the boolean evidence field. This is neither an
MPLADS compliance threshold nor proof of wrongdoing.

# 9. Peer Benchmark Findings

Twenty distinct interpretable metrics are benchmarked. PRE_SANCTION uses 3,
EXECUTION uses 20, and COMPLETION uses 18 after stage exclusions. The union is:

- recommended, technical-estimate, and sanctioned amounts;
- estimate/recommendation, sanction/recommendation, and sanction/estimate ratios;
- released total, largest-payment share, expenditure/sanction percentage, and
  financial-overrun percentage;
- latest physical and financial progress, financial-minus-physical and
  expected-minus-physical gaps;
- decrease count, maximum physical drop, and 30-day physical velocity; and
- days since payment, overdue days, and schedule elapsed ratio.

`peer_benchmark_evidence.csv` contains 51,552 long-form rows. Of those, 1,262 meet
the statistical peer-outlier evidence heuristic. `peer_benchmark_summary.csv`
contains one row for every one of the 3,000 works. These counts are evidence
counts, not risk scores, and repeated metric evidence is not automatically added
into a project risk value.

# 10. Isolation Forest Configuration

Each lifecycle detector uses the same fixed, untuned configuration:

| Parameter | Value |
|---|---|
| `n_estimators` | 300 |
| `max_samples` | `auto` |
| `contamination` | `auto` |
| `random_state` | 42 |
| `n_jobs` | -1 |

Every numeric/boolean matrix is fitted and median-imputed only within its current
lifecycle stage. Boolean 0/1 semantics are preserved. No domain-null field is
globally filled with zero. Exact stage medians, feature lists, exclusions,
versions, row counts, and configuration are stored in model metadata.

Hyperparameters and feature lists were fixed without label access and were not
changed after diagnostic evaluation results were viewed.

# 11. Anomaly Score Semantics

`iforest_score_samples_raw` preserves scikit-learn's original orientation.
`iforest_unusualness_score` is its negative, so higher means more unusual.

Within each lifecycle, unusualness is converted to a deterministic 0–100
percentile and descending rank. A percentile of 100 means among the most unusual
works in that lifecycle; 0 means among the least unusual. It is not a probability.
No `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, final flag, or cutoff was created.

Highest-ranked examples, stated only as unusual-pattern examples:

| Lifecycle | Work | Percentile | Rank | Strongest peer context |
|---|---|---:|---:|---|
| PRE_SANCTION | W-002564 | 100.0 | 1 | `recommended_amount_inr` |
| EXECUTION | W-001322 | 100.0 | 1 | `financial_minus_physical_gap_pct_as_of` |
| COMPLETION | W-000675 | 100.0 | 1 | `financial_overrun_pct_as_of` |

Peer context accompanies the model ranking; it is not claimed as an Isolation
Forest feature contribution or causal explanation.

# 12. Detector Outputs

`anomaly_scores.csv` contains exactly 3,000 rows and 3,000 unique work IDs. Its
seven core fields contain raw model score, higher-is-more-unusual score, within-
stage percentile/rank, and population; three peer-summary columns remain separate
context signals.

`anomaly_evidence.csv` supplies each work's strongest available statistical peer
deviation alongside detector context and explicitly describes the evidence as
accompanying—not attributing—the model score.

`anomaly_summary.json` contains the snapshot, stage counts, stage feature counts,
fixed hyperparameters, stage score distributions, peer counts, and artifact
paths. It contains no evaluation metrics or label fields.

# 13. Ground-Truth Firewall

The production modules `feature_selection.py`, `peer_benchmark.py`, `isolation.py`,
`scoring.py`, and `runner.py` neither import the evaluation loader nor reference
the ground-truth filename, injected-label columns, expected-risk fields, or
ground-truth duplicate information.

Only `evaluation.py` imports `load_evaluation_ground_truth()`. Production feature
selection, imputation, peer grouping, model fitting, hyperparameters, scoring,
percentiles, ranks, and model metadata were finalized before the evaluation
module ran. Model metadata records
`ground_truth_used_for_training = false`.

A regression test mocks the evaluation loader to raise `FileNotFoundError` and
then successfully regenerates feature sets, peer evidence, three model artifacts,
and anomaly scores. Ground-truth unavailability therefore cannot break the
production Day-3 detector.

# 14. Evaluation-Only Method

After production artifacts were finalized, `evaluation.py` aligned scores to
labels using `work_id` only and defined:

`has_injected_anomaly = injected_anomaly_count > 0`

The diagnostic score is `within_stage_anomaly_percentile_0_100`. Overall ranking
sorts lifecycle-normalized percentiles descending, with `work_id` as a stable tie
breaker. ROC AUC and Average Precision are calculated only where both classes
exist. Precision/recall diagnostics use the fixed top 1%, 5%, and 10% of that
ranking; no best-looking metric was selected post hoc.

Evaluation columns exist only in `data/processed/evaluation`. They are absent
from project features, production scores, peer summaries, and model artifacts.

# 15. Diagnostic Evaluation Results

These results are same-synthetic-snapshot diagnostic alignment only. They are not
production generalization estimates, not validated fraud-detection accuracy, and
not evidence of real-world efficacy. Labels represent injected synthetic
anomalies and were never used for training or tuning.

| Scope | Positive / rows | ROC AUC | Average Precision |
|---|---:|---:|---:|
| Overall | 358 / 3,000 | 0.714570 | 0.376393 |
| PRE_SANCTION | 8 / 270 | 0.552004 | 0.043701 |
| EXECUTION | 109 / 801 | 0.824853 | 0.529151 |
| COMPLETION | 241 / 1,929 | 0.673866 | 0.377245 |

| Overall ranking slice | Selected | Positives | Precision | Recall |
|---|---:|---:|---:|---:|
| Top 1% | 30 | 25 | 0.833333 | 0.069832 |
| Top 5% | 150 | 81 | 0.540000 | 0.226257 |
| Top 10% | 300 | 132 | 0.440000 | 0.368715 |

# 16. Tests

The complete Day-1 + Day-2 + Day-3 suite contains 48 tests. Day-3 coverage proves:

- the candidate pool and lifecycle domain restrictions;
- three independent models and absence of a global model;
- stage-local zero/near-zero variance and missingness exclusions;
- stage-local median imputation values;
- real peer fallback and the minimum group size;
- safe MAD, IQR, and constant-distribution behavior;
- exactly 3,000 unique scores, 0–100 percentiles, and correct rank orientation;
- absence of probability/verdict fields;
- production source isolation from evaluation labels;
- successful production generation while the evaluation loader is unavailable;
- evaluation output isolation; and
- source and feature snapshot hashes.

Command:

```powershell
$env:AS_OF_DATE = '2026-09-01'
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final result: **48 passed** on Python 3.12.10.

# 17. Source / Feature Integrity

The SHA-256 of `data/processed/project_features.csv` remained:

`760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148`

The existing regression baselines rechecked all 12 CSV files under `Demo-data`;
all hashes remained byte-for-byte unchanged. No source file was written, renamed,
moved, deleted, or overwritten. Production artifacts were written only to
`data/processed` and `code/models/anomaly`; evaluation artifacts were written only
to `data/processed/evaluation`.

# 18. Limitations

- Data and evaluation labels belong to one synthetic snapshot; diagnostic metrics
  cannot establish production performance.
- PRE_SANCTION has only three semantically valid generic inputs and only eight
  injected-positive evaluation rows, so its diagnostic metrics are especially
  uncertain.
- Isolation Forest ranks unusual multivariate patterns but provides no causal
  attribution. Peer evidence is a separate statistical context layer.
- Peer statistics include the focal row and use a prototype minimum cohort size of
  20; both choices require validation on real production distributions.
- Constant cohort distributions intentionally produce no standardized deviation.
- Stage medians and distribution exclusions are specific to this snapshot and must
  be regenerated for a new governed feature snapshot.
- No final anomaly threshold, risk fusion, decision rule, supervised outcome model,
  duplicate detector, compliance engine, explanation layer, API, or UI exists.

# 19. Recommended Day 4

**Duplicate Candidate + Execution Irregularity Intelligence**

Day 4 has not been implemented. Explicit approval is required before proceeding.
