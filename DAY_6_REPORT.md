# DAY 6 REPORT — Delay + Cost-Overrun Predictive Intelligence

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled snapshot: `AS_OF_DATE=2026-09-01`

# 1. Day 6 Goal

Day 6 implemented leakage-safe 25%/50%/75% historical landmark reconstruction,
operational delay and cost-overrun outcomes, target feasibility gates, work-level
splitting, XGBoost primary modelling, a Random Forest baseline, validation-only
sigmoid calibration, landmark-specific evaluation, current execution-work scoring,
non-causal SHAP evidence, persisted model metadata, and regression tests.

The cost-overrun target passed the governed minimum and was fitted. The delay
target did not: it has only 22 negative completed works, below the minimum of 50.
No delay classifier, delay probability, or delay metric was fabricated.

No final risk fusion, trend/hotspot engine, RAG, Grok, FastAPI, frontend, alert
class, automatic corrective action, self-learning, or Day 7 work was implemented.

# 2. Why Current Snapshot Cannot Be Used Directly for Training

`data/processed/project_features.csv` is the frozen runtime state accumulated by
2026-09-01. Completed-work outcome fields and late execution evidence are already
known there. Training from that row to predict its known completion outcome would
leak future information.

Day 6 instead reconstructs features from raw dated operational histories at
landmarks that precede completion. The runtime snapshot is used only to score the
current 801 execution works after the training and evaluation policy is frozen.
Its SHA-256 remains unchanged.

# 3. Historical Landmark Design

For each completed work with a valid positive planned interval:

`landmark = expected_start_date + fraction × (expected_completion_date - expected_start_date)`

where `fraction` is 0.25, 0.50, or 0.75. Fractional-day timestamps are preserved,
so the calculation is exact rather than rounded to a convenient date.

A row is retained only when sanction is visible on/before the landmark and
completion occurs after it. Released payments and progress reports are filtered
to dates on/before the landmark. Actual start is exposed only after it occurs.

Generated landmark counts are:

| Landmark | Delay rows | Cost-overrun rows |
|---:|---:|---:|
| 25% | 1,929 | 332 |
| 50% | 1,929 | 332 |
| 75% | 1,928 | 332 |
| **Total** | **5,786** | **996** |

One completed work is excluded at 75% because its completion outcome was already
known by that landmark.

# 4. Target Definitions

Delay is defined only for works completed by the controlled snapshot:

`delay_outcome = 1 when completion_date > expected_completion_date, else 0`

Cost overrun is defined only when the work is completed, sanctioned amount is
positive, and final expenditure is visible under the established Day-2 policy:

`cost_overrun_outcome = 1 when final_expenditure_inr > sanctioned_amount_inr, else 0`

Final expenditure is treated as visible only when completion marking is visible
by 2026-09-01. This conservative rule excludes 1,597 completion rows whose final
spend exists in the generated source but is not yet visible under the governed
as-of semantics. No 5% or 10% tolerance was invented.

# 5. Leakage Controls

- No model trains from `project_features.csv`.
- Payments, progress, sanction, and actual start are restricted to the landmark.
- Every landmark precedes completion.
- `completion_date`, `actual_duration_days`, and `completion_delay_days` are not predictors.
- Final expenditure builds the cost target only and is not a predictor.
- Raw recommendation, sanction, expected-start, expected-completion, actual-start,
  completion, and landmark calendar values are not predictors.
- `source_current_*` and source-vs-as-of reconciliation fields are excluded.
- Absolute month/year and days-to-the-shared-completion-date artifacts are absent.
- The anomaly ground-truth file, injected anomaly fields, expected-risk fields,
  and duplicate helper are not loaded or used.
- Median imputation is fitted on TRAIN only; calibration is fitted on VALIDATION only.
- TEST was viewed only after features, hyperparameters, and calibration policy were fixed.

# 6. Predictor Feature Sets

The delay and cost-overrun pipelines have independent explicit allowlists. They
currently contain the same 32 point-in-time fields:

1. `recommended_amount_inr`
2. `technical_estimate_amount_inr`
3. `sanctioned_amount_inr`
4. `estimate_to_recommended_ratio`
5. `sanction_to_recommended_ratio`
6. `sanction_to_estimate_ratio`
7. `days_recommendation_to_sanction`
8. `planned_duration_days`
9. `days_sanction_to_expected_start`
10. `released_payment_count_as_of`
11. `released_payment_total_inr_as_of`
12. `largest_payment_inr_as_of`
13. `mean_payment_inr_as_of`
14. `largest_payment_share_as_of`
15. `days_since_last_payment_as_of`
16. `expenditure_to_sanction_pct_as_of`
17. `financial_overrun_amount_inr_as_of`
18. `financial_overrun_pct_as_of`
19. `progress_report_count_as_of`
20. `latest_physical_progress_pct_as_of`
21. `latest_financial_progress_pct_as_of`
22. `latest_expected_progress_pct_as_of`
23. `financial_minus_physical_gap_pct_as_of`
24. `expected_minus_physical_gap_pct_as_of`
25. `physical_progress_decrease_count_as_of`
26. `max_physical_progress_drop_pct_as_of`
27. `physical_progress_velocity_pct_per_30d`
28. `actual_start_available_as_of`
29. `days_since_actual_start_as_of`
30. `days_to_expected_completion_as_of`
31. `schedule_elapsed_ratio_as_of`
32. `landmark_fraction`

For current scoring, `landmark_fraction` is the current planned schedule-elapsed
ratio clipped to the 0–1 range represented in training. Historical payment and
progress formulas were regression-tested against the shared Day-2 aggregations.

# 7. Eligible Training Population

| Target | Eligible works | Positive | Negative | Prevalence | Landmark rows | Result |
|---|---:|---:|---:|---:|---:|---|
| Delay | 1,929 | 1,907 | 22 | 98.8595% | 5,786 | `INSUFFICIENT_SUPERVISED_OUTCOME_DATA` |
| Cost overrun | 332 | 210 | 122 | 63.2530% | 996 | `FEASIBLE` |

The minimum is at least 50 positive and 50 negative works. Delay therefore has
no trained artifacts and no evaluation split. Its labelled modelling rows remain
available for audit with an explicit not-split status.

# 8. Work-Level Train / Validation / Test Split

Cost-overrun work IDs were sorted, then deterministically stratified with
`random_state=42` at work level:

| Partition | Works | Landmark rows |
|---|---:|---:|
| TRAIN | 232 | 696 |
| VALIDATION | 50 | 150 |
| TEST | 50 | 150 |

All three landmarks for a work stay in one partition. Exact sorted IDs and a
SHA-256 for every partition are recorded in
`code/models/predictive/predictive_model_metadata.json`.

# 9. XGBoost Configuration

The fixed primary model is `XGBClassifier` with 300 estimators, depth 4,
learning rate 0.05, subsample 0.8, column subsample 0.8, minimum child weight 5,
L2 regularization 1.0, binary logistic objective, log-loss evaluation, histogram
tree method, `random_state=42`, and `n_jobs=-1`.

TRAIN-only work class counts produce `scale_pos_weight=0.5782312925`. No test-set
tuning occurred.

# 10. Random Forest Baseline

The independent baseline uses 500 trees, minimum leaf size 5, balanced class
weights, `random_state=42`, and `n_jobs=-1`. It uses the identical work split,
predictor list, and TRAIN-only median imputation as XGBoost. It is a baseline
comparison, not a silently substituted primary model.

# 11. Calibration

The XGBoost base probabilities are calibrated by logistic sigmoid/Platt mapping
of their log-odds, fitted only on the 50 VALIDATION works. The fitted coefficient
is -0.4646331 and intercept is 0.9501955.

| Scope | Version | Brier | 10-bin ECE | ROC AUC |
|---|---|---:|---:|---:|
| VALIDATION, all landmarks | Uncalibrated | 0.341827 | 0.331134 | 0.335069 |
| VALIDATION, all landmarks | Calibrated | 0.210194 | 0.152413 | 0.664931 |
| TEST, all landmarks | Uncalibrated | 0.295484 | 0.234793 | 0.545180 |
| TEST, all landmarks | Calibrated | 0.268094 | 0.157243 | 0.454820 |

The negative coefficient reflects an unstable inverse relationship on this small
synthetic validation split. Calibration improves Brier/ECE but reverses ordering,
and therefore reduces held-out AUC. This is retained and reported rather than
retuned after seeing TEST. Both uncalibrated and calibrated probabilities are
persisted. The calibrated values should not be treated as production-ready.

# 12. Delay Model Evaluation

No delay XGBoost, Random Forest, calibration, or 25%/50%/75% test metric exists.
Only 22 negative completed works are available, so fitting would violate the
minimum feasibility rule. Current execution delay probabilities are null and
their applicability is `INSUFFICIENT_SUPERVISED_OUTCOME_DATA`.

# 13. Cost-Overrun Model Evaluation

Every landmark contains the same 50 held-out works and 62% positive prevalence.
The 50% landmark is the primary mid-execution prototype comparison.

| Landmark | Model output | ROC AUC | Average Precision | Brier |
|---:|---|---:|---:|---:|
| 25% | XGBoost uncalibrated | 0.550085 | 0.696365 | 0.290370 |
| 25% | XGBoost calibrated | 0.449915 | 0.590597 | 0.265555 |
| 25% | Random Forest baseline | 0.441426 | 0.604735 | 0.264191 |
| 50% | XGBoost uncalibrated | 0.541596 | 0.699544 | 0.300724 |
| 50% | XGBoost calibrated | 0.458404 | 0.596143 | 0.269484 |
| 50% | Random Forest baseline | 0.441426 | 0.629807 | 0.264468 |
| 75% | XGBoost uncalibrated | 0.544992 | 0.699869 | 0.295358 |
| 75% | XGBoost calibrated | 0.455008 | 0.591635 | 0.269242 |
| 75% | Random Forest baseline | 0.502547 | 0.666766 | 0.253210 |

These are synthetic prototype diagnostic results, not fraud-detection metrics or
nationwide production generalization guarantees. The weak discrimination is a
material limitation, not a reason to tune against the frozen TEST partition.

# 14. Current Execution Predictions

`predictive_scores.csv` has exactly 3,000 unique work IDs. All 801 execution works
receive cost-overrun primary-model probabilities; zero receive delay probabilities.
Pre-sanction rows are `NOT_APPLICABLE_STAGE`, and completion rows are
`OUTCOME_ALREADY_KNOWN`.

The current calibrated cost-overrun probability distribution across execution is:

| Minimum | P25 | Median | Mean | P75 | Maximum |
|---:|---:|---:|---:|---:|---:|
| 0.295453 | 0.596482 | 0.689312 | 0.678848 | 0.778984 | 0.941450 |

Highest model-estimated early-warning examples that are not already over sanction:

| Work | Calibrated probability | Percentile | Strongest raw-model SHAP field |
|---|---:|---:|---|
| `W-002927` | 0.941450 | 100.000 | `planned_duration_days` |
| `W-000076` | 0.932072 | 99.875 | `planned_duration_days` |
| `W-002848` | 0.915677 | 99.750 | `sanction_to_estimate_ratio` |
| `W-001877` | 0.913611 | 99.625 | `planned_duration_days` |
| `W-001231` | 0.912780 | 99.500 | `sanction_to_estimate_ratio` |

They are review-priority examples from a weak synthetic model, not confirmed
overruns, fraud findings, or automated decisions.

# 15. Observed vs Predicted Conditions

- 272 execution works are already overdue as of 2026-09-01.
- 20 execution works are already over sanctioned expenditure based on visible
  released payments.

These are recorded as `already_overdue_as_of` and
`already_over_sanction_as_of`. Observed over-sanction rows use the applicability
label `OBSERVED_OVER_SANCTION` even though model context is retained. They must
not be presented as wholly future predictions. The unavailable delay model does
not obscure the factual overdue flag.

# 16. SHAP Explanation

SHAP TreeExplainer generated one row for each of the 801 currently cost-scored
execution works, retaining the three strongest absolute contributors to the
XGBoost base model output.

For `W-002927`, the calibrated probability is 0.941450. The strongest base-model
contributor is `planned_duration_days=197`, with raw-margin SHAP value -1.001469;
the base-model probability reference is 0.478474. Because validation calibration
learned a negative mapping, the sign of a base-model SHAP contribution must not be
read as the direction of the calibrated probability.

SHAP explains the XGBoost model output only. It is non-causal, does not explain
why the real project will overrun, and proves neither failure nor wrongdoing.

# 17. Model Artifacts

Created under `code/models/predictive`:

- `cost_overrun_xgboost.joblib`
- `cost_overrun_random_forest.joblib`
- `cost_overrun_calibrator.joblib`
- `cost_overrun_imputer.joblib`
- `predictive_model_metadata.json`

No delay model artifact exists because the target failed feasibility.

Created under `data/processed`:

- `modeling/day6/predictive_landmark_snapshots.csv`
- `modeling/day6/delay_training_rows.csv`
- `modeling/day6/cost_overrun_training_rows.csv`
- `evaluation/day6_predictive_metrics.json`
- `evaluation/day6_test_predictions.csv`
- `predictive_scores.csv`
- `predictive_explanations.csv`
- `day6_predictive_summary.json`

Labels exist only in modelling/evaluation artifacts, never in production scores.

# 18. Tests

The Day-6 suite verifies exact landmark construction, pre-outcome inclusion,
future payment/progress/actual-start exclusion, Day-2 formula equivalence,
predictor blacklists, outcome counts, feasibility gating, deterministic stratified
work splits, all-landmarks-together assignment, TRAIN-only imputation,
VALIDATION-only calibration, XGBoost and Random Forest persistence, deterministic
bounded probabilities, lifecycle applicability, observed/predicted separation,
non-causal explanation wording, production label isolation, and frozen hashes.

Command:

```powershell
$env:AS_OF_DATE = '2026-09-01'
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final result: **89 passed in 47.70 seconds** on Python 3.12.10, with no warnings.

# 19. Source / Prior-Artifact Integrity

All 12 CSV files under `Demo-data` retain their recorded SHA-256 hashes. No source
file was modified, renamed, moved, deleted, or overwritten.

Twenty-nine frozen Day-2 through Day-5 artifacts are regression-checked, including
the feature table/catalog/profile, all Day-3 anomaly/peer/model/evaluation outputs,
all Day-4 duplicate/payment/fund-progress outputs, and all Day-5 compliance and
guideline artifacts. They remain byte-identical. Day 6 writes only its new
modelling, evaluation, score, explanation, summary, and predictive-model files.

# 20. Limitations

- Training data is synthetic, and completion outcomes belong to the same generated dataset.
- All 1,929 completed works share the synthetic completion date 2026-08-31.
- Landmark reconstruction reduces leakage but does not create real production longitudinal history.
- Delay is infeasible because only 22 negative outcomes are available.
- Cost-overrun training uses only 332 works with visible final expenditure.
- The held-out cost-overrun discrimination is weak and calibration is unstable.
- The single synthetic split cannot establish robustness across districts, years,
  operational systems, or changing data-generation processes.
- Test results are prototype/synthetic diagnostics, not nationwide production guarantees.
- Delay and cost probabilities are not fraud probabilities, guilt scores, or final risk scores.
- SHAP evidence is model attribution, not causal explanation.

# 21. Recommended Day 7

**Cross-Project Trend Intelligence + Explainable Risk Fusion**

Day 7 has not been implemented. Explicit approval is required before proceeding.

# Day 6.1 Predictive Serving Safety Audit

Audit date: 2026-09-02  
Controlled snapshot: `AS_OF_DATE=2026-09-01`

## Why the calibrated output is unsafe for ranking

The validation-only sigmoid calibrator has coefficient **-0.4646330589**. Its
negative slope reverses XGBoost ordering: a higher raw cost-overrun score becomes
a lower calibrated probability. This is why held-out raw ROC AUC values of
0.550085, 0.541596, and 0.544992 at 25%, 50%, and 75% become 0.449915,
0.458404, and 0.455008 after calibration.

This is not treated as a training bug and did not trigger retraining, label
inversion, alternate calibration selection, threshold tuning, feature changes,
partition changes, or any other test-set optimization. The original metrics and
test predictions remain byte-identical historical evidence.

The governed calibration metadata is now:

- `calibration_status = UNSTABLE_RANK_REVERSAL`
- `calibration_serving_eligible = false`
- calibrated probabilities are retained as `DIAGNOSTIC_AUDIT_ONLY`

## Raw XGBoost serving orientation

Current operational ranking now uses the existing uncalibrated XGBoost output:

- score: `cost_overrun_serving_score`
- source: `cost_overrun_probability_uncalibrated`
- percentile: `cost_overrun_serving_percentile_0_100`
- rank: `cost_overrun_serving_rank`

Higher raw probability produces a higher percentile and a stronger rank, with
rank 1 representing the strongest raw-model warning. The older cost-overrun
percentile aliases were recomputed to the same raw orientation. The calibrated
probability remains present but is never used for serving rank or percentile.

## Updated current warning examples

The top five execution works by raw XGBoost probability, excluding works already
observed over sanction, are:

| Rank | Work | Raw serving score | Serving percentile | Calibrated diagnostic | Strongest raw-model SHAP contributor |
|---:|---|---:|---:|---:|---|
| 1 | `W-002013` | 0.980458 | 100.000 | 0.295453 | `days_recommendation_to_sanction=38`, SHAP 0.674671 |
| 2 | `W-002938` | 0.976728 | 99.875 | 0.313001 | `sanction_to_estimate_ratio=0.992239`, SHAP 1.033325 |
| 3 | `W-001290` | 0.973867 | 99.750 | 0.325001 | `days_sanction_to_expected_start=10`, SHAP 0.938999 |
| 4 | `W-002605` | 0.970183 | 99.625 | 0.338978 | `planned_duration_days=295`, SHAP 0.787055 |
| 5 | `W-001046` | 0.967692 | 99.500 | 0.347652 | `days_recommendation_to_sanction=47`, SHAP 0.744381 |

These are weak prototype early-warning signals for review, not confirmed
cost overruns, final risk classes, or fraud findings.

## SHAP consistency

SHAP continues to explain the raw XGBoost margin. Each explanation now carries
its aligned `raw_model_probability`, declares
`model_output_explained=xgboost_raw_margin`, and states that the calibrated value
is diagnostic and is not explained by SHAP. The serving chain is therefore
coherent: raw XGBoost output → raw-score percentile/rank → SHAP evidence for that
same base model.

## Model-quality and serving status

- Cost overrun: `PROTOTYPE_WEAK_DISCRIMINATION` and
  `RAW_XGBOOST_SECONDARY_EARLY_WARNING_EVIDENCE`.
- Delay: `MODEL_UNAVAILABLE_INSUFFICIENT_CLASS_BALANCE`; no delay probability or
  serving score exists.
- Serving policy: the raw cost signal may be displayed only as secondary
  early-warning evidence and must not dominate future risk fusion.

## Day-7 fusion guardrail

`AGENTS.md` now permanently requires serving and model-quality status to be
considered before any predictive signal enters risk fusion. The unavailable
delay model contributes nothing; the unstable calibrated cost probability is
excluded; the raw cost score is weak secondary evidence only; and observed
overdue/over-sanction conditions remain separate deterministic evidence.

No risk fusion or Day 7 implementation was created during this audit.

## Day 6.1 verification

The full Day-1 through Day-6.1 regression suite completed with **96 passed in
48.26 seconds**. It revalidated all source hashes, prior Day-2 through Day-5
artifacts, frozen Day-6 model binaries, modelling rows, test predictions,
evaluation metrics, and work-partition hashes.
