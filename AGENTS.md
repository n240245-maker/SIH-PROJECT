# Repository Instructions

## PROJECT

SIH26102 MPLADS AI Risk Intelligence Prototype

## PROJECT ROOT

`C:\SIH-PROJECT`

## SOURCE CODE LOCATION

All application source code must live under:

`C:\SIH-PROJECT\code`

## SOURCE DATA

`C:\SIH-PROJECT\Demo-data` must be treated as read-only.

Do not modify, rename, delete, move, or overwrite source files.

## CSV-FIRST MVP

No SQL/database for the MVP.

Do not introduce PostgreSQL, MySQL, MongoDB, SQLite, Redis, pgvector, or another database without explicit approval.

Keep canonical source tables as separate in-memory DataFrames and write generated outputs only to approved output locations such as `C:\SIH-PROJECT\data\processed`.

## GROUND TRUTH

`07_anomaly_ground_truth.csv` is evaluation-only.

Never expose its labels, label-derived values, or evaluation-only helpers to production features or model inputs. Use `work_id` only to align predictions and labels inside isolated evaluation workflows.

## GOVERNANCE

Anomaly does not mean fraud.

Risk score means review priority.

Authorized human officials make final decisions.

## VALIDATION-TO-RISK SAFETY

- Validation issue row counts are not risk scores.
- Multiple warnings for one work must not automatically multiply its risk.
- `FUTURE_ACTUAL_EVENT` is a temporal/data-context quality observation and may be a synthetic artifact.
- Future feature engineering must aggregate validation signals at work level rather than treating issue rows as independent project risks.
- Later risk fusion must decide explicitly whether and how data-quality signals contribute to review priority.

## EXPLANATION PROVIDER

GroqCloud is the configured on-demand provider for the grounded RAG/explanation
layer. The approved model is `openai/gpt-oss-120b`; no substitute model may be
selected silently. No external tools, browser search, code execution, or provider
retrieval may be enabled.

The hosted model is explanation-only. Models, statistics, and deterministic rules
perform core detection and compliance. Core detection and deterministic fallback
must work without Groq or an API key.

## ENGINEERING RULES

- Implement one module at a time.
- Run tests after every module.
- Do not modify unrelated modules.
- Do not invent model metrics.
- Do not invent MPLADS rules.
- Use deterministic checks where exact rules/formulas are sufficient.
- Keep payments and progress as separate one-to-many tables.
- Never create a naive giant works/payments/progress feature merge.
- Production feature tables must be one row per work where required.
- Report architectural changes before implementing them.

## ASSET CARDINALITY

The current `06_assets_compliance.csv` prototype has one row for each completed
work, with unique `asset_id` and `work_id`. This is an observed prototype-data
property, not a universal MPLADS rule. Future project-profile code must aggregate
asset records safely if real data contains multiple assets for one work.

## FEATURE SNAPSHOT SAFETY

`data/processed/project_features.csv` is a runtime/current as-of project feature
snapshot. It is not automatically a valid supervised training dataset for delay,
cost-overrun, or other outcome prediction. Supervised training requires historical
time-aware snapshots and outcomes constructed without future-information leakage.

- Do not create supervised targets from this runtime snapshot without explicit approval.
- Prefer dated payment, progress, and closure histories for as-of dynamic features.
- Source-current work fields are reconciliation context unless separately justified.
- `duplicate_group_reference` and all ground-truth-derived fields are blacklisted from model features.

## LIFECYCLE-AWARE MODEL SELECTION

Future anomaly models must not automatically select every catalog column where
`model_eligible=true` or `generic_anomaly_eligible=true`. Eligibility defines an
audited candidate pool, not an automatic model matrix or a claim of optimality.

- Route works by lifecycle stage before selecting model inputs.
- `PRE_SANCTION` selection may use only information available before sanction.
- `EXECUTION` selection may use as-of payment, progress, and schedule information.
- `COMPLETION` selection may use completion-specific information after its event dates.
- A feature valid in one lifecycle stage may be meaningless or constant in another.
- Constant, near-constant, synthetic-artifact, routing, reconciliation, and compliance-only fields require explicit exclusion or dedicated deterministic handling.

## DAY-3 DETECTOR GOVERNANCE

- Production anomaly detection uses three independent lifecycle Isolation Forests; no global all-stage model is permitted.
- Model preprocessing is fitted within each lifecycle stage and current Day-3 numeric/boolean missingness is handled by stage-local medians.
- Isolation Forest unusualness, within-stage percentile, and peer robust deviation are separate detector signals. Do not average them into a risk score without a later governed risk-fusion design.
- A peer group minimum of 20 and the absolute robust-deviation heuristic of 3.5 are statistical engineering choices, not MPLADS rules or compliance thresholds.
- Peer evidence accompanies a model score but is not an Isolation Forest feature contribution or causal attribution.
- Production feature selection, preprocessing, training, scoring, ranking, and metadata must remain operational when evaluation ground truth is unavailable.
- Only `code/intelligence/anomaly/evaluation.py` may explicitly load evaluation ground truth. Evaluation results must remain under `data/processed/evaluation` and must never be used to retune the same Day-3 detector.

## DAY-4 DETECTOR GOVERNANCE

- Duplicate detection produces review candidates only. It never confirms that two works are duplicates or establishes intent or wrongdoing.
- Production duplicate modules must not access `duplicate_group_reference`, evaluation ground truth, or label-derived values. Semantic weights and the prototype threshold must be fixed without helper labels.
- Work-description embeddings are generated locally. Project text must not be sent to an external LLM, embedding API, or vector database.
- Missing coordinates or amounts remain missing evidence; they must not be converted to zero distance or zero amount similarity.
- Payment chronology, final-payment consistency, post-completion payments, and released-total evidence are review signals, not automatic compliance findings.
- The 25-percentage-point large-gap band and two-consecutive-report persistence band are prototype engineering heuristics, not MPLADS rules.
- Duplicate similarity, payment evidence counts, fund-progress gaps, Day-3 anomaly scores, and peer deviations remain independent signals. Do not create a fused score or final class until a later explicitly governed step.
- Later work must load the frozen Day-3 model artifacts and scores rather than retraining them merely because evaluation metrics are known.

## GUIDELINE CURRENTNESS AND COMPLIANCE

- Compliance rules and later RAG must reference a verified, versioned guideline document.
- PDF file metadata timestamps must never be interpreted as guideline edition dates.
- Compliance decisions must be produced by deterministic, manually verified rules; an LLM may explain existing evidence but may not decide compliance.
- If the official guideline changes, every new or changed rule requires clause-level re-verification.
- The prior rule registry remains versioned, and previously generated compliance results must not be silently rewritten against a new guideline edition.

## DAY-6 PREDICTIVE GOVERNANCE

- Supervised delay and cost-overrun models may train only on reconstructed point-in-time landmark snapshots; the frozen Day-2 runtime snapshot is for current scoring, not historical training.
- Every training landmark must precede the work outcome and may use only payments, progress, sanction, and actual-start information visible by that landmark.
- Raw/derived completion outcomes, final expenditure, absolute calendar dates, source-current reconciliation fields, anomaly labels, and duplicate helper fields are prohibited predictors.
- Train/validation/test assignment is at work level. Imputation is fitted on train only, calibration on validation only, and test results must not be used for tuning.
- A target with fewer than 50 positive or 50 negative eligible works is marked `INSUFFICIENT_SUPERVISED_OUTCOME_DATA`; no classifier or metric may be forced.
- Current observed overdue or over-sanction conditions must remain distinct from model-estimated future warning probabilities.
- Predictive probabilities are early-warning estimates, not fraud probabilities, guilt findings, final risk scores, or guarantees of production generalization.
- The shared synthetic completion date (2026-08-31) and single generated dataset materially limit external validity even after landmark reconstruction.
- Predictive signals may enter later risk fusion only when serving status and model-quality status are explicitly considered.
- The unavailable delay model contributes no predictive model signal.
- The unstable calibrated cost-overrun probability must not enter risk fusion or operational ranking; it is retained for diagnostic audit only.
- Raw cost-overrun XGBoost output may be used only as weak, secondary early-warning evidence because held-out discrimination is weak.
- Observed overdue and observed over-sanction conditions remain separate deterministic evidence and must not be relabelled as predictions.

## DAY-7 REVIEW-PRIORITY GOVERNANCE

- Review-priority scores and bands prioritize records for authorized human review; they are not probabilities, findings of wrongdoing, or automatic decisions.
- Policy version `REVIEW_PRIORITY_POLICY_V0_1` uses fixed lifecycle weights. Do not tune them from ground truth, helper labels, evaluation metrics, or the observed score distribution.
- Detector-hotspot prevalence is dashboard and management context only. It must never feed back into an individual work score.
- Operational trend context may contribute only from causal, supported operational-event trends; synthetic completion/closure dates are prohibited trend inputs.
- `RELEASED_TOTAL_EXCEEDS_SANCTION` belongs only to the observed-conditions family and must not also contribute through payment execution.
- Repeated evidence rows are reduced within their family; family scores are capped at 100 and are not multiplied by raw evidence counts.
- The calibrated cost-overrun probability remains diagnostic-only. Only the raw-XGBoost serving percentile may contribute, at no more than five EXECUTION points.
- The unavailable delay model contributes exactly no predictive signal and has no Day-7 policy weight.
- Evidence coverage is reported separately. It never rescales or multiplies review priority, and missing evidence does not trigger weight renormalization.
- Strong deterministic detector alerts remain visible even when the fused score is below the HIGH queue band.

## DAY-9 APPLICATION GOVERNANCE

- Backend role scope is authoritative. STATE requires a state, DISTRICT requires a state and district, and MP requires an `mp_id`; the frontend selector is not a security boundary.
- Frozen Day-2 through Day-8.2 artifacts are loaded read-only and indexed at application startup. One-to-many evidence remains separate and must not be expanded into a giant work/payment/progress merge.
- Work-detail contribution points must reproduce the frozen Review Priority score before the record is served.
- Queue, dashboard, and alert counts are decision-support summaries. They are not probabilities, findings, verdicts, or automated decisions.
- The default explanation is the deterministic local fallback. Groq may be contacted only through the explicit explanation POST initiated by a user action; ordinary browsing must remain offline-capable.
- Provider errors, rate limits, timeouts, absent credentials, invalid schemas, or failed grounding must return a safe fallback without exposing credentials, prompts, payloads, or stack traces.
- `GROQ_API_KEY` remains server-side. Frontend code, frontend environment files, OpenAPI output, runtime logs, and generated application summaries must not contain it.
- Officer reviews are append-only records. Every appended review has a corresponding append-only audit event; changing analytical artifacts or silently overwriting review history is prohibited.
- Evaluation ground truth and helper labels are prohibited from application repositories, API contracts, UI responses, scope options, and review workflow decisions.
- Server-side pagination and bounded evidence/trend responses are required. Full 3,000-work detail payloads must never be sent to the browser.

## DAY-9.1 PRESENTATION AND REPORT GOVERNANCE

- Field-level warning styling must be driven only by existing governed evidence. A large value alone does not authorize an alert or a red state.
- Observed/deterministic strong issues, REVIEW conditions, analytical signals, contextual information, PASS, NOT_APPLICABLE, and INSUFFICIENT_DATA must remain visually and semantically distinct. REVIEW is never relabelled NON_COMPLIANT.
- Raw metric, family, rule, evidence, chunk, and model-quality identifiers belong in optional technical details; the primary officer view uses centralized friendly labels and one-decimal display formatting.
- Work-detail chronology may visualize only existing structured event evidence. Planned future dates are not anomalies merely because they are future.
- Quantitative case-brief and report facts come from structured backend evidence. Groq may explain only the explicitly supplied evidence and remains explicit-action-only.
- Downloading a case report must never call Groq. Reports use the deterministic fallback unless an already validated GROQ_GROUNDED response for the exact work/evidence/guideline/model/prompt key exists in the process-local safe cache.
- Case-review PDFs are prototype decision-support documents, not official orders, audit findings, adjudications, certificates, or legal conclusions.

## DAY-9.2 LIFECYCLE AND ATTENTION GOVERNANCE

- Day-7 Review Priority scores, weights, bands, ranks, detector outputs, rule results, prediction outputs, and trend outputs remain frozen. Attention Level is presentation-only and must never feed back into them.
- `CRITICAL`, `HIGH`, and `MEDIUM` map to Immediate Priority, High Attention, and Medium Attention. A `LOW` work is Normal only when no current actionable alert exists; otherwise it is Low Attention.
- Requires Review means current actionable observed or deterministic evidence: a compliance REVIEW/NON_COMPLIANT result, observed overdue/over-sanction condition, payment or fund-progress review, corroborated duplicate candidate, or another governed actionable alert. Anomaly, peer, trend, or cost-prediction evidence alone does not set it.
- Validation issue row counts are not risk or review scores. Multiple warnings for a work must not multiply review urgency automatically; work-level aggregation and the frozen fusion policy remain authoritative.
- Raw false document booleans are not automatic failures. UC, handover, public-use, photo, and asset-register presentation must follow their exact deterministic rule and lifecycle; `NOT_APPLICABLE` completion requirements in PRE_SANCTION or EXECUTION display neutrally as Expected after completion.
- Financial exceedance magnitude is presentation-only: at or below 0% Normal; above 0–5% Low Attention; above 5–15% Requires Review; above 15–30% High Attention; above 30% Very High Attention. This scale does not alter alert presence, compliance, or Review Priority.
- Primary UI prose uses friendly evidence, metric, severity, trend, model-state, and document-state metadata. Raw rule IDs, evidence codes, feature names, robust statistics, and model enums remain available only under technical details.
- Groq remains explicit-action-only, capped at eight selected evidence items and an 18 KB request, with no tools/search/retry. Grounding validation and the prohibited-verdict firewall must not be weakened.
