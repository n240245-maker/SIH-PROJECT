# 1. Goal

This pre-Day-10 upgrade turns the application into an officer-facing `TRACE-X KAVACH` MPLADS operations portal while preserving the governed analytical pipeline. It adds a complete MP-to-District recommendation workflow, simplifies the normal interface, and keeps recommendations separate from frozen analytical works. Implementation and verification were completed locally; deployment was subsequently authorized explicitly after local review. No Day-10 work was performed.

# 2. UI Simplification

The primary experience now focuses on works, recommendations, progress, payments, compliance, alerts, reviews, documents, locations, status, and officer actions. Long research-style language was shortened, empty states are explicit, and normal screens no longer lead with implementation details.

The final visible brand is `TRACE-X KAVACH` with the subtitle `MPLADS Monitoring & Management Platform`. The supporting footer line is `Track works, review issues, and take action from one place.`

# 3. Removed Visible Technical/Demo Language

Normal application chrome no longer shows the former prototype/demonstration disclaimer, AI-provider status, model names, prompt/generation modes, or fallback badges. The operational frontend has no visible occurrences of the requested unwanted phrases, including `synthetic demo-v2`, `prototype environment`, `Generated locally`, `No Groq call`, `GROQ_GROUNDED`, `DETERMINISTIC_FALLBACK`, or `Methodology`.

Two raw backend state identifiers remain only as internal lookup keys in `frontend/lib/presentation.ts`; they map to friendly officer labels and are never rendered. Demonstration-data truth remains documented in technical files. Source values that themselves contain names such as “Demo District” remain unchanged because source data is read-only.

# 4. Role-Specific Navigation

- MP: Home, Recommend Work, My Works, Alerts.
- District: Home, New Recommendations, Active Works, Review Queue, Compliance, Alerts.
- State: Home, Districts, Review Queue, Trends, Alerts.
- MoSPI: National Overview, Review Queue, States, Trends, Alerts.

Dashboard cards and primary actions also adapt to role. MP sees personal work counts, District sees recommendation-processing cards including Under Review, State sees Districts Needing Attention, and MoSPI sees national operational summaries.

# 5. MP Recommendation Workflow

`/recommend-work` provides a four-step form: Work Details, Location, Cost & Evidence, and Pre-Check. Values remain in React state while the MP moves between steps. Submission displays the generated recommendation ID and links to the new record and My Works.

Fields include title, sector, sub-sector/work type, purpose, expected public benefit, state, district, block, village/locality, optional pincode, optional coordinates, Proposed Project Cost, optional expected duration, optional preferred start period, supporting document, and site photo.

# 6. Recommendation Pre-Check

The server stores an auditable, lifecycle-appropriate pre-check containing its version, timestamp, completeness result, similar-work result, peer cost context, location result, and applicable pre-sanction rule result. The overall user label is Looks Good, Check Required, or Missing Details. No new Review Priority score is created for a recommendation.

The pre-check sends no data to Groq or any other external service and exposes no model/provider/prompt details.

# 7. Similar Works Check

The query reuses the frozen Day-4 local work embeddings and loads the existing local sentence-transformer only when a pre-check is requested. It does not rebuild the 3,000-work baseline index. Candidates combine bounded text similarity with sector/sub-sector, location-distance, and amount context. At most five sanitized candidate records are returned, labelled as possible similar works rather than confirmed duplicates.

# 8. Cost Comparison

Proposed Project Cost is compared with available comparable-work amounts. The interface reports peer context such as within the observed range or higher than comparable works. No unverified official maximum or invented MPLADS threshold was introduced.

# 9. Location / Geo Verification

MP state and district are prefilled from the selected MP scope. Latitude and longitude must be supplied together and are range-validated. `Use Current Location` requests browser geolocation only after an explicit button action; it is never collected silently.

For uploaded images, EXIF GPS is extracted when genuinely present. The service calculates distance from the recommended coordinates and reports Location Match or Location Difference using the configured 0.5 km review distance. Missing EXIF remains unavailable, and the UI states that a location match does not prove image authenticity.

# 10. Documents & Photos

The workflow accepts PDF, JPG/JPEG, and PNG files up to 10 MB. The backend checks the document-type allowlist, filename confinement, extension, media type, file signature, base64 validity, and byte limit. Files receive randomized stored names under the confined runtime upload directory, with SHA-256 and safe metadata. Arbitrary filesystem paths are not returned. Non-image documents display `Stored securely`; only image files receive photo-location wording.

# 11. District Recommendation Workflow

District officers receive only recommendations inside their backend-enforced state/district scope. They can request clarification, accept a recommendation for processing, enter sanction and schedule details, add progress, add payments, and mark an in-progress record completed. An MP cannot sanction its own recommendation, and a District cannot access another District’s record.

The local browser flow completed recommendation, clarification, response, acceptance, sanction, progress, payment, and completion successfully.

# 12. My Works

`/my-works` is MP-only and combines existing analytical works with runtime recommendations at the service/UI layer. It provides Recommended, Ongoing, Completed, and Needs Attention tabs plus search by ID, title, or location. Existing analytical rows and runtime recommendation rows remain separate in storage.

# 13. Runtime Lifecycle

Recommendation IDs use deterministic sequential formatting such as `REC-000001`. Supported states are Draft, Recommended, Under Review, Needs Clarification, Accepted, Sanctioned, In Progress, Completed, and Closed. The tracker shows completed, current, and future stages distinctly and never treats a recommendation as a sanctioned historical work merely because it was submitted.

# 14. Field-Level Warning Highlighting

Warning styling is driven by structured governed evidence rather than raw magnitude alone:

- released payments above sanction: red field with the exceedance reason;
- financial/physical gap of at least 25 percentage points: amber attention fields;
- authorization before payment request: highlighted payment row with reason;
- overdue expected completion for a non-completed record: red schedule field with days;
- compliance REVIEW: amber; NON_COMPLIANT: red; PASS/NOT_APPLICABLE/INSUFFICIENT_DATA: neutral or positive;
- peer/statistical-only evidence: subtle amber, never a guilt/fraud finding.

Browser checks opened `W-001937`, `W-001966`, and `W-002240`, confirmed the complete case sections, and confirmed no blanket red styling. The isolated runtime record also generated separate Payments, Payments & Progress, and Payment Dates alerts from entered evidence; no score multiplication or risk-policy change was introduced.

# 15. Case Summary Simplification

The work page now uses `Case Summary` and an explicit `Explain This Case` button. The default summary is deterministic and structured from current backend evidence. Normal browsing never contacts Groq. The existing grounding, verdict firewall, eight-item evidence cap, 18 KB payload cap, and deterministic fallback remain unchanged.

# 16. Recent Activity

Recommendation creation, document storage/location checks, pre-check, submission, clarification, acceptance, sanction, progress, payment, and completion append events to JSONL history. Events are shown with friendly title-cased labels, actor, timestamp, and administrative detail. Existing officer review history remains append-only.

# 17. Backend API Changes

Typed routes added:

- `POST /api/v1/recommendations`
- `GET /api/v1/recommendations`
- `GET /api/v1/recommendations/my-works`
- `GET /api/v1/recommendations/{recommendation_id}`
- `POST /api/v1/recommendations/{recommendation_id}/precheck`
- `POST /api/v1/recommendations/{recommendation_id}/actions`
- `POST /api/v1/recommendations/{recommendation_id}/documents`
- `GET /api/v1/recommendations/{recommendation_id}/activity`

Health reports analytical and runtime counts separately. The local baseline health check returned 3,000 analytical works and one isolated browser-smoke recommendation.

# 18. Runtime Storage

Runtime data is isolated under `data/runtime` when used normally:

- `recommendations.json`: current recommendation snapshots;
- `recommendation_events.jsonl`: append-only lifecycle events;
- `uploads/`: randomized confined attachments.

Browser verification used `tmp/pre-day10-runtime` so it did not populate the normal runtime directory. Frozen CSVs and analytical artifacts are never updated by recommendation actions. Storage uses a process-local lock and atomic JSON snapshot replacement.

# 19. Security

Backend scope enforcement, typed validation, restricted media types, signature validation, 10 MB limits, basename rejection, randomized storage names, resolved-path confinement, safe errors, and server-side provider credentials are preserved. The secret audit found zero credential-name, token-prefix, bearer-header, or secret-value matches in production frontend, runtime records, and generated application artifacts. Ground-truth/helper terms were absent from recommendation code, API artifacts, frontend routes, and runtime records.

# 20. Tests

- Focused recommendation backend tests: 15 passed.
- Existing Day-9 backend regressions: 39 passed.
- Full Python suite: 243 passed, with one dependency deprecation warning from the installed Starlette/httpx bridge.
- Frontend tests: 11 passed.
- All 12 immutable Demo-data SHA-256 values matched the pinned baseline.

The tests cover IDs, required fields, invalid cost/coordinates, MP and District scope, bounded pre-checks, provider/ground-truth isolation, clarification/acceptance, sanction/progress/payment, append-only activity, secure upload rejection paths, runtime/frozen separation, report wording, and all earlier governed functionality.

# 21. Frontend Build

`npm run lint` passed. `npm run build` passed with successful TypeScript checking and static generation. Final routes are `/`, `/alerts`, `/my-works`, `/new-recommendations`, `/recommend-work`, `/recommendations/[recommendationId]`, `/review-queue`, `/trends`, and `/works/[workId]`. `/methodology` is absent.

The recommendation form was visually checked at 1280, 1024, and 768 px. Labels, controls, step indicator, and Continue action remained visible; tables retain bounded internal scrolling and no accidental page-wide horizontal overflow was observed.

# 22. Existing Feature Regression

Local browser and automated checks covered MoSPI, State, District, and MP scopes; dashboards; Review Queue; alerts; Area Trends; work details; duplicate candidates; payment/progress evidence; compliance; observed/predictive presentation; case summary; review and activity history; and the current-page CSV export control. Local case-report generation returned HTTP 200, `application/pdf`, a `%PDF` signature, and 7,279 bytes. No explanation POST was made during ordinary browsing.

# 23. Frozen Artifact Integrity

There are zero working-tree diffs under `Demo-data`, `data/processed-v2`, `models`, or `code/models`. The full regression suite revalidated the existing Day-2 through Day-9 invariants. Frozen scores remain unchanged, including `W-001937 = 89.441901` and `W-002760 = 78.928155`; the High/Critical queue remains 1,104. Existing Day-9.2 attention counts remain Normal 378, Low Attention 189, Medium 1,329, High 1,096, Immediate Priority 8, and Requires Review 2,470.

Only the Day-9 application contract was legitimately regenerated. `data/processed/application/openapi.json` now contains the recommendation routes, and `pre_day10_product_upgrade_summary.json` records local verification with no secrets.

# 24. Known Limitations

- The role selector demonstrates scoped behavior; it is not production authentication.
- Runtime JSON/JSONL storage is appropriate for the local CSV-first MVP but not multi-instance transactional deployment.
- Geolocation requires browser permission, and many images do not contain trustworthy EXIF GPS.
- Similar-work and peer-cost results are review aids, not duplicate or compliance determinations.
- No live Government system connection is claimed.
- Source records contain demonstration place/person names that remain visible as data values because source files are immutable.
- The repository currently contains both the original 3,000-work governed baseline and a later 5,000-work `demo_v2` profile. The baseline invariant and hashes are unchanged; the frontend’s established default selects `demo_v2`. Runtime recommendations remain separate from both. The intended profile should be explicitly confirmed before Day 10 rather than silently rewriting either frozen profile.
- Attachment preview/download and production-grade object storage remain future deployment concerns.

# 25. Ready for Day 10

The requested pre-Day-10 product upgrade is complete and verified locally. The MP-to-District lifecycle is operational, normal UI language is simplified, core analytics remain available, and frozen/source integrity is intact. After reviewing the local Recent Activity redesign, the user explicitly authorized pushing the verified upgrade to the existing deployment pipeline. No production environment variable change, model retraining, analytical regeneration, or Day-10 implementation was performed.

## Deployment Addendum — 7 September 2026

The Recent Activity section was refined into a compact vertical timeline with left-aligned content, newest-action emphasis, actor metadata, deterministic IST timestamps, and a responsive mobile layout. Frontend tests, lint, TypeScript, and the production build passed before deployment authorization was acted upon.
