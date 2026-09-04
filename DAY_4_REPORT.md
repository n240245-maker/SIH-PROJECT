# DAY 4 REPORT — Duplicate Candidate + Execution Irregularity Intelligence

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled snapshot: `AS_OF_DATE=2026-09-01`

# 1. Day 4 Goal

Day 4 implemented only local duplicate-work candidate retrieval, deterministic
payment irregularity evidence, fund-versus-physical-progress reconciliation,
persistent reported-gap evidence, detector-specific artifacts, and regression
tests.

Duplicate output means **duplicate candidate for review**, not a confirmed
duplicate. Payment and execution outputs describe irregularity, inconsistency, or
unusual review evidence; they do not establish intent, wrongdoing, or a compliance
decision.

No final risk fusion, fraud verdict, compliance engine, guideline RAG, Grok,
supervised delay/overrun model, SHAP, frontend, FastAPI, or automatic investigation
decision was implemented.

# 2. Dependencies

Only the two approved Day-4 direct dependencies were added to `pyproject.toml` and
installed in the project Python 3.12 environment:

| Direct dependency | Declared constraint | Resolved version |
|---|---|---:|
| sentence-transformers | `>=3.4,<6` | 5.7.0 |
| geopy | `>=2.4,<3` | 2.5.0 |

Sentence Transformers installed its required local inference stack, including
PyTorch 2.13.0+cpu, Transformers 5.16.1, Tokenizers 0.23.1, Hugging Face Hub
1.29.0, and supporting packages. PyTorch is present only for the explicitly
approved semantic-embedding requirement. No FAISS, vector database, LangChain,
Grok/xAI SDK, FastAPI, XGBoost, or SHAP dependency was added.

# 3. Files Created / Modified

Created source packages:

- `code/intelligence/duplicates/__init__.py`
- `code/intelligence/duplicates/text.py`
- `code/intelligence/duplicates/similarity.py`
- `code/intelligence/duplicates/detector.py`
- `code/intelligence/duplicates/runner.py`
- `code/intelligence/payments/__init__.py`
- `code/intelligence/payments/irregularities.py`
- `code/intelligence/execution/__init__.py`
- `code/intelligence/execution/fund_progress.py`
- `code/intelligence/execution/runner.py`
- `code/tests/test_day4.py`
- `DAY_4_REPORT.md`

Created generated artifacts:

- `data/processed/duplicate_work_embeddings.npy`
- `data/processed/duplicate_work_embeddings_metadata.json`
- `data/processed/duplicate_candidates.csv`
- `data/processed/duplicate_summary.csv`
- `data/processed/payment_irregularities.csv`
- `data/processed/payment_irregularity_summary.csv`
- `data/processed/fund_progress_evidence.csv`
- `data/processed/day4_detector_summary.json`
- local embedding-model cache under `code/models/duplicates/`

Modified `pyproject.toml`, `AGENTS.md`, `README.md`, and the Day-3 test fixture.
The fixture modification prevents the complete regression suite from retraining or
rewriting frozen Day-3 models; it now loads existing artifacts. Empty `.gitkeep`
files in the implemented duplicate/payment packages were removed.

# 4. Duplicate Detection Design

The detector explicitly selects safe operational work fields and never uses a
works/payments/progress giant merge. It constructs one semantic-search text per
work from:

- work description;
- sector and sub-sector; and
- state, district, block, and village.

Normalization uses Unicode NFKC, lowercase/casefold, light punctuation cleanup,
hyphen/underscore separation, and whitespace normalization. It does not remove
potentially distinguishing project or geographic words.

Cosine `NearestNeighbors` retrieval obtains the ten nearest non-self works for
each of 3,000 works. Pairs are canonicalized as lexicographically ordered work
IDs, duplicates from reciprocal retrieval are collapsed, and each pair appears
once. Retrieval and scoring run locally in memory; no vector database or external
project-text API is used.

# 5. Semantic Embeddings

Embedding model:

`sentence-transformers/all-MiniLM-L6-v2`

The model generated exactly 3,000 normalized float32 embeddings of dimension 384
on CPU. The array occupies 4,608,128 bytes. Metadata records the ordered work IDs,
text contract hash, normalization policy, library version, model name, dimension,
and explicit no-evaluation-label/no-external-text-API flags.

Embeddings are persisted so repeat production runs can reproduce retrieval without
re-encoding when model name, ordered work IDs, and normalized-text SHA-256 match.
The local model cache contains approximately 91.6 MB. The first model download
used public Hugging Face model storage; work descriptions themselves were never
sent to Hugging Face or another external service.

# 6. Structured Duplicate Evidence

Every retrieved pair independently records:

- cosine text similarity;
- same state, district, block, and village flags;
- WGS-84 geodesic distance;
- recommended and sanctioned amount similarities;
- absolute recommendation-date difference;
- sector and sub-sector matches; and
- implementing-agency match.

Amount similarity is:

`1 - abs(a - b) / max(abs(a), abs(b))`

bounded to 0–1 when the denominator is positive. Recommended and sanctioned
amount similarities are combined with weights 0.60 and 0.40 over available
values. Missing sanctioned amounts therefore do not become zero similarity.

Missing or invalid coordinates produce null distance, never zero distance.
Geographic distance is converted to a 25-km linear proximity component only when
available. All raw components remain in `duplicate_candidates.csv`.

# 7. Duplicate Scoring Formula

The deterministic candidate-priority score is:

`100 × weighted_available_mean(`  
`0.50 × text_cosine_similarity,`  
`0.15 × location_similarity,`  
`0.15 × amount_similarity,`  
`0.10 × date_proximity,`  
`0.05 × sector_match,`  
`0.03 × sub_sector_match,`  
`0.02 × implementing_agency_match)`

Missing components are omitted and remaining weights are renormalized; missing
evidence is never treated as a zero-value mismatch.

Supporting components are:

- `location_similarity = weighted_available_mean(0.40 same_state, 0.25 same_district, 0.15 same_block, 0.10 same_village, 0.10 max(0, 1 - distance_km / 25))`
- `amount_similarity = weighted_available_mean(0.60 recommended_similarity, 0.40 sanctioned_similarity)`
- `date_proximity = max(0, 1 - recommendation_date_difference_days / 365)`

`candidate_flag=true` when score is at least 75.0. This was fixed before output
inspection as a prototype retrieval threshold. It was not optimized with helper
labels and is not an MPLADS rule, legal threshold, probability, or confirmation.

# 8. Duplicate Candidate Findings

| Finding | Result |
|---|---:|
| Works embedded | 3,000 |
| Unique canonical pairs evaluated | 18,290 |
| Pairs at/above prototype threshold | 11,763 |
| Works with at least one flagged candidate | 2,995 |
| Minimum pair score | 58.054002 |
| Median pair score | 77.000644 |
| Mean pair score | 77.224743 |
| 90th percentile | 84.498453 |
| Maximum pair score | 96.033758 |

Highest-priority examples, stated only as candidates:

| Pair | Score | Evidence synopsis |
|---|---:|---|
| W-002680 / W-002722 | 96.033758 | identical Solar Water System text/location; 0.230 km; amount similarity 0.9758; dates 58 days apart |
| W-000740 / W-000892 | 95.673732 | Solid Waste Shed variants at the same named village/block/district; 0.204 km; amount similarity 0.9781; dates 36 days apart |
| W-002973 / W-002984 | 95.610570 | Community Hall wording variants at the same named location; 0.102 km; amount similarity 0.9832; dates 55 days apart |
| W-002299 / W-002340 | 95.359006 | Public Waiting Hall wording variants at the same named location; 0.244 km; amount similarity 0.9365; dates 21 days apart |
| W-000431 / W-000564 | 95.323240 | Health Sub-Centre wording variants at the same named location; 0.119 km; amount similarity 0.9925; dates 74 days apart |

The broad candidate count reflects intentionally repetitive synthetic descriptions
and locations. It is not a claim that 11,763 pairs are true duplicates.

# 9. Payment Irregularity Rules

Payment evidence uses only released rows visible by 2026-09-01 and reuses the
audited canonical order:

1. `work_id`
2. `payment_release_date`
3. natural numeric `payment_stage`
4. `payment_id`

Implemented signal codes:

- `PAYMENT_AUTH_BEFORE_REQUEST`
- `PAYMENT_RELEASE_BEFORE_AUTH`
- `DUPLICATE_PFMS_REFERENCE`
- `ZERO_VALUE_RELEASED_PAYMENT`
- `PAYMENT_AFTER_COMPLETION`
- `PAYMENT_AFTER_FINAL_PAYMENT`
- `MULTIPLE_FINAL_PAYMENTS`
- `RELEASED_TOTAL_EXCEEDS_SANCTION`

Payment-after-completion compares each visible release with
`completion_date_as_of` and retains amount and days after completion. Later
payments following a final marker and additional final markers are determined in
canonical sequence. All are consistency/review evidence; legitimate settlement
timing may exist.

# 10. Payment Findings

| Signal | Evidence rows |
|---|---:|
| PAYMENT_AUTH_BEFORE_REQUEST | 711 |
| PAYMENT_RELEASE_BEFORE_AUTH | 0 |
| DUPLICATE_PFMS_REFERENCE | 1 |
| ZERO_VALUE_RELEASED_PAYMENT | 1 |
| PAYMENT_AFTER_COMPLETION | 0 |
| PAYMENT_AFTER_FINAL_PAYMENT | 0 |
| MULTIPLE_FINAL_PAYMENTS | 0 |
| RELEASED_TOTAL_EXCEEDS_SANCTION | 1,215 |
| **Total** | **1,928** |

There are 1,574 works with at least one payment-evidence row. The reduction from
some Day-1 source-wide counts is expected because Day 4 excludes future releases
at the controlled snapshot. Evidence counts remain separate signal occurrences;
they are not summed into a final project risk score.

# 11. Fund-vs-Progress Design

For every work with a positive sanctioned amount, payment-based financial
progress is:

`released_payment_total_inr_as_of / sanctioned_amount_inr × 100`

The preferred physical value is `latest_physical_progress_pct_as_of`. The signed
current gap is:

`fund_minus_physical_gap_pct_as_of = payment_based_financial_progress_pct_as_of - latest_physical_progress_pct_as_of`

A positive value means released funds are ahead of observed physical progress; a
negative value means physical progress is ahead of released expenditure. Zero or
missing sanction denominators are not divided.

Latest reported financial progress is also compared with physical progress and
with payment-based financial progress:

`reported_vs_payment_financial_progress_difference_pct = latest_reported_financial_progress_pct_as_of - payment_based_financial_progress_pct_as_of`

This is reconciliation evidence between two sources, not a statement that either
source is necessarily wrong.

# 12. Persistence Evidence

Visible progress rows are sorted by work, report date, and progress ID. For every
report:

`reported_gap = financial_progress_pct - physical_progress_pct`

Per work, the engine retains latest, maximum, and mean gap; positive and large-gap
report counts; latest consecutive large-gap run; and maximum consecutive run.

The large positive gap band is 25 percentage points and persistent evidence means
at least two consecutive reports meeting it. These values were fixed before output
inspection as prototype engineering review heuristics, not official MPLADS rules.

Current findings:

- 1,448 works have at least one run of two consecutive reported gaps at or above
  25 points.
- 69 works currently have payment-based financial progress at least 25 points
  ahead of latest physical progress.

# 13. Execution Findings

Fund-progress output contains 2,730 sanctioned works.

| Signed payment-based fund-minus-physical gap statistic | Percentage points |
|---|---:|
| Minimum | -16.000000 |
| Q1 | -3.391903 |
| Median | 0.711261 |
| Mean | 1.331151 |
| Q3 | 4.604369 |
| P90 | 6.004369 |
| Maximum | 129.416222 |

Reported-vs-payment financial-progress differences are tightly centered around
zero in this synthetic snapshot: median 0, mean -0.001078, minimum -0.987467,
and maximum 0.05 percentage points.

Specific status consistency fields preserve interpretable Day-1 evidence rather
than copying validation-warning counts:

- 6 works are marked not started while visible payments exist.
- 9 works are marked not started while non-zero physical progress exists.

# 14. Ground-Truth / Helper Firewall

Production source under `duplicates`, `payments`, and `execution` does not import
or reference the evaluation loader, ground-truth filename, injected-label fields,
expected-risk fields, or the duplicate helper field.

Duplicate text, embeddings, nearest neighbors, structured evidence, weights,
threshold, scores, and candidate flags were generated without helper labels. Tests
drop the helper column entirely and still build normalized text and candidate
evidence successfully. Production detection remains independent if the isolated
ground-truth CSV is unavailable.

The optional duplicate evaluation was deliberately skipped: no clean real-world
evaluation definition exists in the current inputs, and inventing one from helper
metadata would risk misleading claims or post-result tuning.

# 15. Outputs

| Artifact | Rows / shape | Purpose |
|---|---:|---|
| `duplicate_work_embeddings.npy` | 3,000 × 384 | normalized local semantic vectors |
| `duplicate_work_embeddings_metadata.json` | metadata | model, text contract, ordered IDs, formula and threshold |
| `duplicate_candidates.csv` | 18,290 pairs | continuous similarity and structured pair evidence |
| `duplicate_summary.csv` | 3,000 works | flagged candidate count and best candidate |
| `payment_irregularities.csv` | 1,928 evidence rows | long-form payment signals |
| `payment_irregularity_summary.csv` | 3,000 works | per-code and total evidence counts |
| `fund_progress_evidence.csv` | 2,730 works | signed gaps, reconciliation, persistence, status consistency |
| `day4_detector_summary.json` | summary | counts, distributions, heuristic definitions, artifact paths |

Duplicate, payment, fund-progress, anomaly, and peer signals remain separate. No
output contains `risk_score`, `risk_class`, or final severity classes.

# 16. Tests

The complete Day-1 through Day-4 suite contains 61 tests. Day-4 coverage includes:

- one normalized embedding per work;
- no self-pairs and canonical pair uniqueness;
- cosine, amount, and final score ranges;
- null-safe coordinate distance;
- deterministic weighted scoring;
- successful duplicate core operation without the helper column;
- production source scans for helper/ground-truth access;
- numeric Stage ordering and exclusion of future releases;
- authorization/request, release/authorization, PFMS, zero-value,
  post-completion, post-final, multiple-final, and total-exceeds-sanction signals;
- safe sanction denominators and exact fund-progress formulas;
- consecutive-gap persistence and reported/payment reconciliation;
- absence of final risk fields; and
- frozen source, feature, anomaly-score, metadata, and Day-3 model hashes.

Command:

```powershell
$env:AS_OF_DATE = '2026-09-01'
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final result: **61 passed in 16.59 seconds** on Python 3.12.10. The suite loaded
the existing Day-3 models and did not retrain them.

# 17. Source / Prior-Artifact Integrity

All 12 `Demo-data` CSV hashes remain unchanged. Key frozen artifacts remained:

| Artifact | SHA-256 |
|---|---|
| `project_features.csv` | `760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148` |
| `anomaly_scores.csv` | `F65777B89067A8335AA953255C448774D7E52F08728B7455A4C9FBA7DF91D4CC` |
| `anomaly_model_metadata.json` | `FA07C130E2BB37CA354922DE72F5872FA5DBE5F50FFF012A7919601E19349B1F` |
| pre-sanction model | `A87EBECFA83E1DF9A52614FDCEAA038D7E7D87DEAEAF1231864CE3D1C6F54529` |
| execution model | `C7267BD53FB0EEC426CE572FDBC6D17FBC9925A21485962FA20EFC3E47DEFFCD` |
| completion model | `48C9C6AF5384C2C9CC19B55FD012A56CC73357F49611101FFF5A81250C78C86B` |

No source CSV, Day-2 feature value, Day-3 score, Day-3 metadata field, or Day-3
model artifact was modified by Day 4.

# 18. Limitations

- The dataset is synthetic and heavily templated. High semantic similarity and
  repeated named locations create many candidates; 11,763 flagged pairs must not
  be interpreted as confirmed duplication.
- The 75-point candidate threshold and score weights are engineering choices that
  have not been calibrated against real adjudicated duplicate cases.
- Nearest-neighbor retrieval evaluates a local top-10 candidate set, not every
  possible pair; true candidates outside that neighborhood may be missed.
- Some synthetic named districts/blocks are geographically broad or inconsistent
  with coordinate distances. Raw distance and exact-name fields are both retained
  so reviewers can see the conflict.
- The public embedding model can change upstream. Persisted embeddings and text
  contract hashes improve this run's reproducibility, but a production registry
  should pin an immutable model revision.
- Payment chronology and post-completion timing can have legitimate administrative
  explanations and require source-document review.
- The 25-point/two-report persistence policy is not an official threshold, and the
  current high persistence count is influenced by synthetic progress generation.
- No real duplicate-label evaluation, compliance decision, final threshold
  calibration, risk fusion, API, or user interface exists.

# 19. Recommended Day 5

**MPLADS Compliance Rule Engine + Guideline Evidence Foundation**

Day 5 has not been implemented. Explicit approval is required before proceeding.

# Day 4.1 Duplicate Selectivity Audit

## Scope and outcome

This unlabeled calibration audit separates nearest-neighbor retrieval from a
small officer review queue. It did not consult `duplicate_group_reference`,
ground truth, injected anomaly fields, or any label-derived value. It did not
retrain or rewrite Day-3 models. The continuous
`duplicate_similarity_score_0_100`, its deterministic formula, and the historical
`candidate_flag = score >= 75` semantics are unchanged.

All 18,290 nearest-neighbor pairs remain in `duplicate_candidates.csv` with
`retrieval_candidate = true`. The original rule still marks 11,763 pairs and
2,995 works. The new corroborated `review_candidate` policy selects 14 pairs
representing 24 distinct works.

## Score distribution

The score is analytical evidence on a 0–100 scale, not a probability.

| Statistic | Score |
|---|---:|
| Minimum | 58.054002 |
| P50 | 77.000644 |
| P75 | 80.788587 |
| P90 | 84.498453 |
| P95 | 86.635740 |
| P97.5 | 88.244030 |
| P99 | 90.302163 |
| Maximum | 96.033758 |

| Diagnostic cutoff | Pair count at or above cutoff |
|---:|---:|
| 80 | 5,426 |
| 85 | 1,572 |
| 90 | 209 |
| 92.5 | 49 |
| 95 | 6 |

These cutoffs are distribution diagnostics only. They were not evaluated or
optimized against helper labels.

## Structured-evidence audit

High total scores alone remain too broad in this synthetic, heavily templated
dataset. At score >=85, text similarity is very high but the median geographic
distance is 133.307 km and only 10.31% of pairs share a village. Even at score
>=90, the median distance is 114.228 km and only 23.44% share a village. At
score >=92.5 all pairs share a district, but median distance is still 38.136 km
and only 57.14% share a village. This supports requiring independent structured
corroboration instead of using the composite score alone.

| Score tier | Pairs | Text median | Distance median / P90 km | Amount P10 / median | Date median / P90 days | Same district / block / village | Sector / sub-sector | Agency match |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| >=85 | 1,572 | 0.996306 | 133.307 / 227.045 | 0.660566 / 0.879672 | 65 / 189.9 | 54.58% / 30.34% / 10.31% | 100% / 100% | 23.73% |
| >=90 | 209 | 0.996446 | 114.228 / 223.385 | 0.800046 / 0.949672 | 48 / 137.4 | 93.30% / 51.20% / 23.44% | 100% / 100% | 29.19% |
| >=92.5 | 49 | 0.994916 | 38.136 / 202.080 | 0.926900 / 0.971542 | 59 / 133.4 | 100% / 79.59% / 57.14% | 100% / 100% | 22.45% |
| >=95 | 6 | 0.986128 | 0.199 / 0.237 | 0.955172 / 0.976917 | 56.5 / 66 | 100% / 100% / 100% | 100% / 100% | 0% |

## Exact deterministic review policy

A pair enters the prototype review queue only when every condition below holds:

- composite similarity score is at least 90;
- text cosine similarity is at least 0.97;
- district, block, and village all match;
- geographic distance is present and no more than 1.0 km;
- combined amount similarity is present and at least 0.90;
- recommendation-date difference is present and no more than 120 days; and
- sector and sub-sector both match.

Implementing-agency match is retained as visible evidence but is not required.
Only 29.19% of score >=90 pairs match on agency, and none of the six score >=95
pairs do; making it mandatory would remove the strongest locally and financially
corroborated examples without evidence that agency identity is a necessary
duplicate condition.

This is a conservative engineering policy for selecting records for human
inspection. It is not an MPLADS rule, a probability, a legal conclusion, an
identity determination, or a finding of wrongdoing. `review_policy_reason`
records the deterministic pass result or every failed condition for each pair.

## Highest-scoring review examples

| Pair | Score | Text | Distance km | Amount similarity | Date difference days |
|---|---:|---:|---:|---:|---:|
| `W-002680` / `W-002722` | 96.033758 | 1.000000 | 0.229571 | 0.975772 | 58 |
| `W-000740` / `W-000892` | 95.673732 | 0.980027 | 0.204378 | 0.978063 | 36 |
| `W-002973` / `W-002984` | 95.610570 | 0.987522 | 0.102157 | 0.983162 | 55 |
| `W-002299` / `W-002340` | 95.359006 | 0.978017 | 0.243654 | 0.936542 | 21 |
| `W-000431` / `W-000564` | 95.323240 | 0.989413 | 0.118618 | 0.992473 | 74 |

Every example also has matching district, block, village, sector, and sub-sector.
They are review evidence only.

## Output and dashboard changes

`duplicate_candidates.csv` adds `retrieval_candidate`, `review_candidate`, and
`review_policy_reason` while preserving all retrieved evidence and the historical
flag. `duplicate_summary.csv` preserves the original candidate count and best-pair
fields and adds `review_candidate_count`, `best_review_candidate_work_id`,
`best_review_similarity_score_0_100`, and the work-level `review_candidate` flag.
`day4_detector_summary.json` now records the complete distribution, threshold
counts, structured-evidence audit, exact policy, and old/new queue sizes.

## Payment and fund-progress guardrail

No Day-4 payment or fund-progress detector logic was modified. In particular,
`RELEASED_TOTAL_EXCEEDS_SANCTION` and persistent fund-progress-gap counts remain
detector evidence, not direct risk classes. The 25-percentage-point gap and
two-consecutive-report policy remains explicitly a prototype engineering
heuristic rather than an MPLADS rule.

## Regression and integrity result

Four new tests verify score-formula continuity, deterministic corroboration,
failure when any documented condition is absent, queue/retrieval subset behavior,
and identity-safe output wording. The existing production-source firewall,
frozen-artifact hashes, and Demo-data hash checks remain active.

Full result on Python 3.12.10: **65 passed in 7.83 seconds**. All 12
`Demo-data` CSV hashes, `project_features.csv`, `anomaly_scores.csv`, Day-3 model
metadata, and all three Day-3 model hashes remain unchanged. Ground truth and the
duplicate helper remained outside production scoring and review calibration.
