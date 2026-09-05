# Post-Deployment SIH Improvements

Project: MPLADS Sentinel — SIH26102

Phase: P0 officer usability and decision-support improvements

Snapshot date: 2026-09-01

Starting baseline: `caa771d82dfc2a966fa27df64bf80d46c1acd077` (`day10-deployed-pass`)
Working branch: `post-deployment-improvements`

## Phase status

P0 is implemented and locally verified. P1 and P2 are deferred until P0 is committed, deployed, and verified in the hosted environment. This phase does not retrain a model, regenerate an analytical artifact, change a detector or rule, or change Review Priority or Attention Level policy.

## P0 changes

### Officer-facing work detail

The work dossier now follows this compact information hierarchy:

1. Case at a Glance
2. Why This Work Needs Attention
3. Warnings & Review Signals
4. Fund Utilization & Payments
5. Progress & Schedule
6. Records & Completion Readiness
7. MPLADS Compliance
8. Duplicate Work Review
9. Comparison With Similar Works
10. Forecast / Predictive Signal
11. AI-Assisted Case Explanation
12. Officer Review & Corrective Action

Large cards are reserved for the overall priority and high-level case summary. Facts, dates, financial values, warnings, rules, records, and peer comparisons use rows, lists, or tables. Exact contribution points, thresholds, identifiers, raw scores, percentiles, robust deviations, and raw precision are under collapsed technical details.

Records and completion readiness are grouped as Recorded, Requires Review, Not Recorded, and Not Applicable. Rows are expandable without nested cards. Not Applicable uses a neutral icon and wording rather than warning treatment.

The visible reason list describes actual governed conditions. Frozen score composition is retained only in technical details. The former “Early Warnings” wording is now “Warnings & Review Signals.” Trend context is no longer a primary case section; supported context may appear in a collapsed “Recent Reporting Context” disclosure with an explicit non-evidentiary disclaimer.

### Numerical presentation

Officer-facing scores, percentages, and percentage-point gaps use one decimal place. Financial fields use exact Indian grouping and, where a short summary is useful, lakh/crore notation. Stored values and frozen calculations are unchanged; exact values remain available in technical details and backend artifacts.

### Fund utilization health

The case page now presents estimated cost, visible sanction, released amount, recorded expenditure when available, physical and financial progress, the finance-versus-physical gap, the released-versus-sanction difference, and the percentage above sanction.

The status uses the existing Day-9.2 presentation policy only:

- at or below 0%: Normal
- above 0% through 5%: Low Attention
- above 5% through 15%: Requires Review
- above 15% through 30%: High Attention
- above 30%: Very High Attention

This status does not change Review Priority or create a new compliance result.

### Monitoring health and evidence availability

The backend now derives a presentation-only eight-dimension summary from existing governed evidence: Finance, Physical Progress, Schedule, Payments, Compliance, Duplicate Review, Completion Records, and Evidence Availability.

Evidence Availability is deterministic. Expected-after-completion and not-applicable records are excluded from the denominator. At least 75% available is Good, 50% through less than 75% is Moderate, and less than 50% is Limited. It does not affect Review Priority. A broader data-quality dashboard remains deferred to P1.

### Alert Center

New route: `/alerts`.

The backend supplies grouped summaries from the existing frozen alert artifact. Categories are Financial, Progress, Schedule, Payments, Compliance, Duplicate Review, and Analytical Signals. Each row shows the distinct-work count, status, and a controlled explanation. Actionable governed conditions remain distinct from statistical, peer, prediction, and trend context. Selecting a row opens the Review Queue with the corresponding evidence filter applied.

Alert row counts are not risk scores and do not multiply case urgency.

### Corrective action workflow

Officer reviews remain append-only. A review now requires one allow-listed follow-up action and may record the active role/scope label:

- Request Clarification
- Request Supporting Documents
- Financial Reconciliation Required
- Request Updated Progress Report
- Schedule / Field Verification
- Duplicate Work Comparison Required
- Review Revised Sanction
- Escalate for Detailed Review
- No Further Action
- Close After Verification

The backend validates the action enum, appends it to the review record, and includes it in the corresponding append-only audit event. Groq cannot invent or select an action. No automatic escalation is implemented. The Render Free JSONL store remains ephemeral and may reset after a restart or redeploy.

### AI explanation

The primary explanation has only About this work, What happened, and Main issues. The default remains the immediate deterministic local fallback. Groq remains optional, uses `openai/gpt-oss-120b`, and is contacted only after the officer presses the explicit generation button. Navigation and PDF generation never call Groq. Existing Day-8.2 grounding, allow-list, payload cap, validation, verdict firewall, and fallback behavior are unchanged.

### PDF alignment

The deterministic case-review PDF now follows the same officer-facing hierarchy, readable precision, and plain-language issue summaries. It does not include a primary operational-trend section, secrets, NaN values, stack traces, a fraud conclusion, or an automatic action. An already validated process-local Groq result may be reused only under the existing exact cache contract; generating the PDF never calls Groq.

## Accessibility improvements

- status uses icon and text, not color alone
- native `details`/`summary` disclosures are keyboard operable
- disclosure controls have descriptive `aria-label` text
- neutral treatment is used for Not Applicable and insufficient/context states
- tables retain semantic rows and cells
- focus-visible styles are present
- compact controls retain usable click/tap targets
- responsive rules stack monitoring, readiness, and alert groups
- the document has no page-level horizontal overflow in the desktop browser smoke test

## Backend presentation fields

The following response additions are presentation-only and are derived from frozen evidence:

- `presentation.monitoring_health`
- `presentation.evidence_availability_rule`
- `presentation.financial.estimated_cost_inr`
- `presentation.financial.recorded_expenditure_inr`
- `presentation.financial.health_interpretation`
- `presentation.warning_signals[].display_order`
- `/api/v1/alerts.summary[]`
- review `follow_up_action` and `scope_label`

No analytical score, band, rank, alert membership, rule result, duplicate candidate, prediction, peer threshold, or trend value is recomputed by these fields.

## Verification

Local verification on 2026-09-04:

- Python: 217 passed; one known Starlette deprecation warning
- frontend: 11 passed
- ESLint: PASS
- Next.js production build: PASS
- PDF regressions: 5 passed
- browser console: zero application errors
- Alert Center navigation/filter handoff: PASS
- keyboard readiness disclosure: PASS
- page-level horizontal overflow: none at the tested desktop viewport
- mobile breakpoint: PASS at Chrome's 504-pixel minimum CSS viewport; document and body widths matched the 489-pixel client area, while the section navigation and peer table remained locally scrollable
- deterministic fallback: PASS
- automatic Groq calls during navigation/PDF: none

Required local cases checked: `W-001937`, `W-002760`, `W-000933`, `W-001437`, `W-000476`, and `W-000012`.

Frozen acceptance values remain:

- `W-001937`: 89.441901
- `W-002760`: 78.928155
- Normal: 378
- Low Attention: 189
- Medium Attention: 1,329
- High Attention: 1,096
- Immediate Priority: 8
- Requires Review: 2,470
- frozen high/critical queue: 1,104

All 12 `Demo-data` SHA-256 values match the immutable test baseline. Evaluation ground truth remains isolated. No generated analytical artifact, model, embedding, rule registry, or source CSV was changed.

## Deployment and rollback

- frontend: https://mplads-sentinel-one.vercel.app
- backend: https://mplads-sentinel-api.onrender.com
- backend health: https://mplads-sentinel-api.onrender.com/health
- stable rollback tag: `day10-deployed-pass`
- earlier rollback tag: `day9.2-predeployment`
- P0 checkpoint commit message: `P0 post-deployment usability and decision-support improvements`

Hosted P0 verification follows the normal branch/commit deployment flow. Render Free may cold-start and the review/audit JSONL store is not durable.

## Deferred work

P1 remains deferred: role-specific dashboard emphasis, broader evidence/data-quality dashboards, normalized state/district comparisons, aggregate fund utilization, deterministic schedule-slippage and utilization-trajectory analytics, enhanced model health, verification suggestions, trends-page expansion, and production-scale architecture documentation.

P2 remains deferred: saved views, enhanced exports, cohort/history/map analysis, advanced combined filters, multilingual explanation, case Q&A, role summaries, and drift-monitoring extensions.

The current production architecture remains CSV/frozen artifacts, pandas, FastAPI, and Next.js. It is a decision-support prototype, not a claim of nationwide production readiness.
