# DAY 7 REPORT — Cross-Project Trend Intelligence + Explainable Review-Priority Fusion

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled snapshot: `AS_OF_DATE=2026-09-01`  
Policy version: REVIEW_PRIORITY_POLICY_V0_1`

# 1. Day 7 Goal

Day 7 implemented cross-project operational trends, separate current detector
hotspots, one-row-per-work operational trend context, transparent lifecycle-aware
review-priority fusion, fixed priority bands, reconstructable contribution
evidence, a HIGH/CRITICAL officer queue, problem-specific alerts, authority
summaries, and regression tests.

No Grok, RAG, LLM explanation, FastAPI, frontend, authentication, officer-workflow
write, self-learning, automatic investigation decision, or Day 8 work was
implemented.

# 2. Governance

Review priority means that multiple evidence families make a work more important
for authorized human review. It is not a probability, final finding, guilt score,
or automatic decision. The weights and bands are prototype engineering policy,
not official MPLADS classifications.

Production Day-7 code does not load `07_anomaly_ground_truth.csv`, evaluation
loaders, injected-anomaly fields, expected-risk fields, or
`duplicate_group_reference`. Neither weights nor thresholds were tuned against
ground truth or prior evaluation metrics.

# 3. Operational Trend Design

The trend engine uses only validated event histories visible by the controlled
snapshot. It creates dense monthly series over each group's active history, so a
zero-activity month is represented rather than silently skipped.

Groups are produced for state, state + district, sector, state + sector, and state
+ district + sector. District values include state in their encoded key to prevent
same-named districts from being combined across states.

All events after `AS_OF_DATE` are excluded. September 2026 is an incomplete month
and is excluded from trend comparison. The latest complete month is **2026-08**.

# 4. Monthly Event Streams

Seven monthly metrics were created:

| Event stream | Metrics |
|---|---|
| Recommendation | `recommendation_work_count`, `recommended_amount_inr` |
| Sanction | `sanction_work_count`, `sanctioned_amount_inr` |
| Released payment | `released_payment_count`, `released_payment_amount_inr` |
| Progress | `progress_report_count` |

The engine deliberately does not create completion, UC, audit, handover, or
public-use trends because the source has known synthetic closure-date artifacts.
Actual-start trends were not included because they were optional and would require
additional data-quality caveats.

# 5. Causal Baseline

Each group/metric/target month is compared only with up to six previous complete
months. The target month never enters its own baseline. At least four valid prior
months and 20 historical events across the lookback are required before a
standardized deviation may be emitted. These are engineering support policies,
not MPLADS rules.

# 6. Robust Trend Statistics

Every eligible baseline records median, MAD, Q1, Q3, IQR, P10, and P90. The signed
deviation is:

- `0.6745 × (current - median) / MAD` when MAD is positive;
- `(current - median) / (IQR / 1.349)` when MAD is zero and IQR is positive; and
- null when MAD and IQR are both zero, preventing a fabricated deviation.

EWMA uses fixed `alpha=0.30`. `abs(robust_z) >= 3.5` marks
`OPERATIONAL_TREND_DEVIATION` as a statistical engineering heuristic only.

# 7. Trend Findings

`trend_timeseries.csv` contains **71,445** group/metric/month rows and
`trend_alerts.csv` contains **1,309** historical operational trend deviations.
There are **274** supported deviations in the latest complete month. Work context
maps 2,910 works to a latest-month deviation in their most-specific supported
group; the other works retain a zero context contribution.

The strongest latest-month examples are synthetic progress-report surges:

| Group | Metric | August value | Prior median | Signed robust z |
|---|---|---:|---:|---:|
| Sector: Sports | Progress report count | 389 | 101.5 | 193.9188 |
| Telangana / Demo District 2 | Progress report count | 167 | 47.5 | 161.2055 |
| Maharashtra / Sports | Progress report count | 60 | 15.0 | 60.7050 |
| Maharashtra / Demo District 2 | Progress report count | 119 | 31.0 | 59.3560 |
| Telangana / Demo District 4 | Progress report count | 140 | 30.0 | 49.4633 |

These findings reflect the synthetic event generator and are operational context,
not evidence against every work in the group.

# 8. Detector Hotspots

`detector_hotspots.csv` contains **74** groups meeting the 20-work denominator:

| Group type | Groups |
|---|---:|
| State | 6 |
| District | 24 |
| Sector | 8 |
| Implementing agency | 36 |

Each row retains work count and separate counts/shares for top-decile anomaly,
duplicate review, payment evidence, persistent fund gap, observed overdue,
observed over-sanction, compliance review, and deterministic non-compliance.
Shares are decimal proportions from 0 to 1. No opaque hotspot score exists.

# 9. No-Feedback Guardrail

Detector hotspot prevalence is dashboard and management context only. It is not
accepted by `build_work_trend_context`, `build_family_signals`, or the fusion
formula and therefore cannot raise the scores of works that created the aggregate.
Only independently calculated operational time-series context receives a small
policy weight.

# 10. Risk-Fusion Policy

For each lifecycle:

`review_priority_score = Σ(family_weight_pct × family_score / 100)`

Weights are never renormalized when evidence is missing. Absence of evidence does
not become evidence of risk. `fusion_evidence_coverage_pct` separately reports the
share of lifecycle policy weight whose source evidence was evaluable and never
multiplies the score.

Fixed bands are LOW `[0,25)`, MEDIUM `[25,50)`, HIGH `[50,75)`, and CRITICAL
`[75,100]`. They are officer-queue bands, not fraud levels.

# 11. Signal Family Definitions

| Family | Normalized evidence |
|---|---|
| ANOMALY | Day-3 within-stage anomaly percentile directly; not probability |
| PEER_DEVIATION | Lifecycle-local percentile of maximum absolute robust deviation, only when peer-outlier evidence exists |
| DUPLICATE_REVIEW | Day-4.1 `review_candidate` only, using best review similarity |
| PAYMENT_EXECUTION | Maximum of non-over-sanction payment severity and positive fund-progress percentile with at most 10 persistence points |
| OBSERVED_CONDITIONS | Already-overdue and already-over-sanction facts; not predictions |
| COMPLIANCE | Strongest actionable deterministic result, not summed rule rows |
| COST_OVERRUN_PREDICTION | Raw-XGBoost serving percentile only, as weak secondary evidence |
| OPERATIONAL_TREND_CONTEXT | Supported latest-complete-month operational trend-deviation strength |

The unavailable delay model has no family and contributes exactly zero.

# 12. Lifecycle Weights

| Lifecycle | Family weights |
|---|---|
| PRE_SANCTION | ANOMALY 30%; PEER_DEVIATION 25%; DUPLICATE_REVIEW 25%; OPERATIONAL_TREND_CONTEXT 20% |
| EXECUTION | ANOMALY 10%; PEER_DEVIATION 10%; DUPLICATE_REVIEW 15%; PAYMENT_EXECUTION 25%; OBSERVED_CONDITIONS 20%; COMPLIANCE 10%; COST_OVERRUN_PREDICTION 5%; OPERATIONAL_TREND_CONTEXT 5% |
| COMPLETION | ANOMALY 8%; PEER_DEVIATION 7%; DUPLICATE_REVIEW 15%; PAYMENT_EXECUTION 20%; COMPLIANCE 40%; OPERATIONAL_TREND_CONTEXT 10% |

Every map sums to 100%. Because the Day-6 cost model has weak synthetic held-out
discrimination (ROC AUC about 0.54), its maximum EXECUTION contribution is only
five points.

# 13. Normalization Rules

Peer evidence is reduced to one strongest-deviation value per work before a
lifecycle-local percentile is calculated. Repeated peer rows are not separate
risk points. Broad Day-4 `candidate_flag` values do not enter fusion; only the 24
works with corroborated Day-4.1 `review_candidate=true` receive duplicate-family
scores.

Payment severities map INFO/WARNING/STRONG_WARNING to 25/60/90. The current
positive fund-minus-physical gap receives an applicable-population percentile;
persistence adds at most 10 points, and the family uses the maximum of payment and
gap components, capped at 100.

Observed overdue maps to `50 + 0.5 × overdue-days percentile`; observed
over-sanction maps to `75 + 0.25 × financial-overrun-percent percentile`; the
family takes the maximum. Compliance maps NON_COMPLIANT to 100 and REVIEW
INFO/WARNING/STRONG_WARNING to 30/60/80; PASS, NOT_APPLICABLE, and
INSUFFICIENT_DATA contribute zero while availability remains visible.

# 14. Double-Counting Controls

- `RELEASED_TOTAL_EXCEEDS_SANCTION` is excluded from PAYMENT_EXECUTION and assigned
  only to OBSERVED_CONDITIONS.
- Payment irregularity and fund-progress evidence share one capped family and use
  their maximum rather than additive evidence-row counts.
- Anomaly and peer signals can be correlated and are not claimed to be statistically
  independent; each is reduced to one capped family contribution and remains visible.
- Completion compliance timing and observed overdue cannot overlap in the policy:
  observed overdue applies only to EXECUTION, while COMPLETION has no observed-condition
  weight.
- Detector hotspot prevalence never enters individual trend context or fusion.

# 15. Review-Priority Distribution

| Scope | Population | LOW | MEDIUM | HIGH | CRITICAL | Mean | Median | P90 | Maximum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Overall | 3,000 | 567 | 1,329 | 1,096 | 8 | 42.2653 | 45.5132 | 60.6846 | 89.4419 |
| PRE_SANCTION | 270 | 127 | 143 | 0 | 0 | 25.6265 | 25.3548 | 38.9506 | 48.2400 |
| EXECUTION | 801 | 440 | 302 | 58 | 1 | 25.8509 | 22.6341 | 46.8585 | 78.9282 |
| COMPLETION | 1,929 | 0 | 884 | 1,038 | 7 | 51.4101 | 51.1992 | 62.6336 | 89.4419 |

The concentration of completion rows in HIGH reflects synthetic closure evidence,
especially strong compliance REVIEW results, and must not be read as nationwide
project-risk prevalence.

# 16. High / Critical Review Queue

`review_priority_queue.csv` contains **1,104** works: 1,096 HIGH and 8 CRITICAL.
LOW and MEDIUM works remain in the full 3,000-row score table. Strong deterministic
alerts also remain available independently when their fused score is below HIGH.

# 17. Top Cases and Contributions

Top ten review-priority works:

| Rank | Work | Lifecycle | Score | Band |
|---:|---|---|---:|---|
| 1 | W-001937 | COMPLETION | 89.441901 | CRITICAL |
| 2 | W-000431 | COMPLETION | 89.024602 | CRITICAL |
| 3 | W-002276 | COMPLETION | 81.620706 | CRITICAL |
| 4 | W-002259 | COMPLETION | 81.065145 | CRITICAL |
| 5 | W-002760 | EXECUTION | 78.928155 | CRITICAL |
| 6 | W-001966 | COMPLETION | 76.060968 | CRITICAL |
| 7 | W-000090 | COMPLETION | 75.812803 | CRITICAL |
| 8 | W-000934 | COMPLETION | 75.087757 | CRITICAL |
| 9 | W-002883 | COMPLETION | 74.610449 | HIGH |
| 10 | W-002873 | COMPLETION | 74.347292 | HIGH |

Exact family contribution points for the top five:

| Work | Family contributions (points) |
|---|---|
| W-001937 | COMPLIANCE 32.000000; PAYMENT_EXECUTION 20.000000; DUPLICATE_REVIEW 14.130249; OPERATIONAL_TREND_CONTEXT 9.160584; ANOMALY 7.900415; PEER_DEVIATION 6.250653 |
| W-000431 | COMPLIANCE 32.000000; PAYMENT_EXECUTION 20.000000; DUPLICATE_REVIEW 14.298486; OPERATIONAL_TREND_CONTEXT 8.521898; ANOMALY 7.917012; PEER_DEVIATION 6.287206 |
| W-002276 | COMPLIANCE 32.000000; PAYMENT_EXECUTION 20.000000; DUPLICATE_REVIEW 14.249755; ANOMALY 7.788382; PEER_DEVIATION 6.122715; OPERATIONAL_TREND_CONTEXT 1.459854 |
| W-002259 | COMPLIANCE 32.000000; PAYMENT_EXECUTION 19.471903; DUPLICATE_REVIEW 14.249755; ANOMALY 7.834025; PEER_DEVIATION 6.049608; OPERATIONAL_TREND_CONTEXT 1.459854 |
| W-002760 | PAYMENT_EXECUTION 25.000000; OBSERVED_CONDITIONS 19.736842; ANOMALY 9.987500; PEER_DEVIATION 9.408284; COMPLIANCE 6.000000; OPERATIONAL_TREND_CONTEXT 4.708029; COST_OVERRUN_PREDICTION 4.087500; DUPLICATE_REVIEW 0.000000 |

Every displayed score equals the sum of its long-form contribution rows.

# 18. Evidence Coverage

Current evidence coverage is 100% for all 3,000 works (minimum, P25, median, mean,
P75, P90, and maximum all equal 100%). This does not affect the score; it only
means every policy family applicable to each work had evaluable source evidence
in the current synthetic snapshot. Future low-coverage works must be presented as
having limited evidence coverage, not interpreted as low risk.

# 19. Outputs

| Artifact | Rows / role |
|---|---|
| `trend_timeseries.csv` | 71,445 causal monthly rows |
| `trend_alerts.csv` | 1,309 operational trend deviations |
| `detector_hotspots.csv` | 74 transparent aggregate groups |
| `work_trend_context.csv` | 3,000 unique works |
| `risk_fusion_policy.json` | policy v0.1, weights, transforms, exclusions, sources |
| `review_priority_evidence.csv` | 19,062 reconstructable family contributions |
| `review_priority_scores.csv` | 3,000 unique work scores |
| `review_priority_queue.csv` | 1,104 HIGH/CRITICAL works |
| `review_alerts.csv` | 8,554 problem-specific work alerts |
| `review_priority_authority_summary.csv` | 38 state/district/sector summaries |
| `day7_intelligence_summary.json` | complete machine-readable Day-7 summary |

Problem-specific alert counts include 1 deterministic NON_COMPLIANT alert, 24
duplicate-review alerts, 272 observed-overdue alerts, 20 observed-over-sanction
alerts, and 78 weak cost-overrun early-warning alerts. Other alert counts are:
2,132 compliance review, 1,454 fund-progress review, 639 payment irregularity,
723 peer deviation, 301 top-decile statistical anomaly, and 2,910 mapped current
operational trend-context alerts.

# 20. Tests

Twenty-nine Day-7 tests cover complete-month and future-event exclusion, causal
baselines, support gates, MAD/IQR/constant behavior, signed direction, closure-date
exclusion, hotspot no-feedback, exact lifecycle families and weights, prediction
serving restrictions, duplicate selectivity, over-sanction double-count prevention,
exact score reconstruction, fixed bands, coverage separation, referential integrity,
deterministic ranks/contributors, language, source firewall, and frozen hashes.

Command:

```powershell
$env:AS_OF_DATE = '2026-09-01'
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Full result on Python 3.12.10: **125 passed in 54.98 seconds**.

# 21. Source / Prior-Artifact Integrity

The runner hashes 24 frozen Day-2 through Day-6.1 input/model/evaluation artifacts
before and after generation and found no change. The full regression suite also
validated the wider frozen Day-2 through Day-6 artifact set and all 12 exact
`Demo-data` SHA-256 baselines. No source CSV, prior detector output, feature table,
model binary, modelling row, evaluation metric, test prediction, or Day-6.1
serving field was modified.

Payments and progress remain separate one-to-many operational tables. Day 7 reads
their validated histories for monthly aggregation and never creates a naive
works/payments/progress merge. Ground truth remains evaluation-only.

# 22. Limitations

- Source data and every observed trend are synthetic; event surges reflect the
  generator and do not establish real operational prevalence.
- Review-priority weights and bands are prototype engineering policy, not official
  MPLADS rules or fraud levels.
- Isolation Forest and peer signals represent statistical unusualness, not proof.
- Duplicate signals are officer review candidates, not confirmed duplicates.
- Deterministic NON_COMPLIANT applies only where encoded rule conditions directly
  support it; other rules may remain REVIEW or INSUFFICIENT_DATA.
- The cost-overrun model is weak synthetic secondary evidence. Its unstable
  calibrated probability is never fused; raw serving percentile contributes at
  most five points.
- The delay model is unavailable and contributes no model signal.
- Detector hotspot prevalence is contextual and never fed back into work scores.
- Some evidence families share underlying financial/progress fields. Fusion is a
  deterministic prioritization policy, not a statistical probability model and
  does not claim full signal independence.
- Complete-month aggregation avoids partial September comparisons but does not
  solve missing ingestion timestamps or synthetic-history limitations.

# 23. Recommended Day 8

**Day 8 — Grok RAG + Guideline-Grounded Explanation Intelligence**

Day 8 has not been implemented. Explicit approval is required before proceeding.
