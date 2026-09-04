# Day 0 Inspection Report

Inspection date: 2026-09-01 (Asia/Calcutta)  
Repository: `C:\SIH-PROJECT`  
Scope: inspection and reporting only. No Day 1 implementation was performed.

# Day 0.5 Recheck — Updated Inputs

Recheck date: 2026-09-01 (Asia/Calcutta)  
Scope: updated-input inspection plus root documentation/configuration files only. Day 1 remains unimplemented.

## Day 0.5 outcome

The two input blockers recorded on Day 0 were rechecked from the current files. `Demo-data/05_progress.csv` now exists and passes its basic structural, primary-key, work-reference, and reporting-agency-reference checks. The guideline PDF has been replaced by a 70-page edition whose text states that it is effective from 1 April 2023 and supersedes previous MPLADS guidelines. `AGENTS.md`, `README.md`, `.gitignore`, and `.env.example` were added at the repository root.

### Updated `05_progress.csv`

- Exact file: `C:\SIH-PROJECT\Demo-data\05_progress.csv`.
- Shape: 14,902 rows x 15 columns; this exactly matches the manifest row count.
- Exact columns and order: `progress_id`, `work_id`, `report_date`, `physical_progress_pct`, `financial_progress_pct`, `expected_progress_pct_by_date`, `execution_stage`, `reported_status`, `reported_by_agency_id`, `photo_reference`, `geo_latitude`, `geo_longitude`, `remarks`, `source_type`, `synthetic_marker`.
- Inferred pandas dtypes: `progress_id:string`, `work_id:string`, `report_date:string/date`, `physical_progress_pct:float64`, `financial_progress_pct:float64`, `expected_progress_pct_by_date:float64`, `execution_stage:string/category`, `reported_status:string/category`, `reported_by_agency_id:string`, `photo_reference:string`, `geo_latitude:float64`, `geo_longitude:float64`, `remarks:string`, `source_type:string`, `synthetic_marker:boolean`.
- Nulls: every one of the 15 columns has 0 nulls (0.000%).
- Keys: 14,902 unique `progress_id` values, 0 duplicate progress IDs, 0 null progress IDs; 2,730 unique work IDs, 0 null work IDs; 36 unique reporting-agency IDs, 0 null reporting-agency IDs.
- Schema/dictionary: exact 15/15 name and order match; no missing or unexpected columns; observed logical types agree with the dictionary. All non-null dates parse.
- Provenance: all 14,902 rows have `source_type=SYNTHETIC_PROTOTYPE` and `synthetic_marker=True`.

### Progress relationship integrity

- `progress.work_id -> works.work_id`: 14,902/14,902 rows matched (100%); unmatched IDs: none; null work IDs: 0; duplicate parent work IDs: 0.
- `progress.reported_by_agency_id -> entities.entity_id`: 14,902/14,902 non-null references matched (100%); unmatched IDs: none; null references: 0.
- Entity-type check: all 14,902 matched reporting-agency references resolve to `IMPLEMENTING_AGENCY`; unexpected entity types: 0.

### Progress chronology and quality

- `report_date` range: 2023-10-16 through 2026-08-31.
- Malformed report dates: 0. Null report dates: 0. Dates after the inspection/as-of date 2026-09-01: 0.
- Reports before work recommendation: 0. Reports before sanction where a sanction exists: 0. Reports after recorded completion: 0.
- Reports before recorded `actual_start_date`: 12 rows across 5 works. Classification: lifecycle inconsistency requiring later validation; it may reflect a data error, revised start date, or synthetic artifact and is not a fraud conclusion.
- `physical_progress_pct`: range 0-100; below 0: 0; above 100: 0; null/non-numeric: 0.
- `financial_progress_pct`: range 0-164.1; below 0: 0; above 100: 4,292; null/non-numeric: 0. Values above 100 are a data-quality/risk signal and need later business-rule interpretation because the underlying synthetic works include expenditure above sanction.
- `expected_progress_pct_by_date`: range 0-100; below 0: 0; above 100: 0; null/non-numeric: 0.
- Consecutive physical-progress decreases: 295 transitions across 220 works; largest observed drop: 12.8 percentage points. These are reported as possible corrections, data errors, or synthetic anomalies and are not automatically changed.
- Consecutive financial-progress decreases: 0. Consecutive expected-progress decreases: 0.
- Same-work/same-report-date duplicate extras: 13. Progress IDs remain unique; later validation must decide whether multiple same-day snapshots are allowed.

### Progress time-series structure

Across all 3,000 works, progress-report counts have minimum 0, median 5, mean 4.9673, and maximum 8. There are 270 works with zero progress records, 24 with exactly one, and 2,706 with multiple progress records. Among the 2,730 works with any progress, the minimum is 1, median 5, mean 5.4586, and maximum 8. This verifies the intended one-work-to-many-progress-updates relationship.

### Actual merge multiplication

- Base works: 3,000 rows.
- `works LEFT JOIN payments`: 10,011 rows.
- `works LEFT JOIN progress`: 15,172 rows.
- Naive `works LEFT JOIN payments LEFT JOIN progress`: 53,640 rows.
- Multiplication factor: 17.88x relative to the 3,000 work rows.

The expanded table was inspected only in memory and was not stored or used for modelling. The architecture must preserve `df_works`, `df_payments`, `df_progress`, `df_assets`, `df_mp`, and `df_entities` separately. Later feature engineering must aggregate each one-to-many history and create `df_project_features` with exactly one row per work.

### Updated guideline

- Exact file: `C:\SIH-PROJECT\guidelines\official_mplads_guidelines.pdf`.
- Size: 1,642,098 bytes.
- Pages: 70; 64 pages have extractable text.
- Extracted text: approximately 109,659 characters, including whitespace; approximately 92,141 non-whitespace characters.
- Extractable title: `MEMBERS OF PARLIAMENT LOCAL AREA DEVELOPMENT SCHEME Guidelines`.
- The PDF text states `APRIL 1, 2023`, `First Edition, 22nd February, 2023`, and `Second Edition, 14th March, 2023`.
- Clause 1.1 states that the guidelines come into force from 1 April 2023 and supersede previous MPLADS guidelines and instructions. Footnotes state revisions to specified paragraphs via a MoSPI circular dated 14 March 2023.
- PDF metadata has a creation timestamp in November 2025, but the document text does not identify a 2025 edition; that metadata is not treated as a publication/revision claim.
- Normal extraction works. Chapters 1-11 and Annexures I-VIII are extractable. OCR is not necessary and was not used.
- This document is clearly newer than the prior November 2005 file. Currentness still requires authoritative verification.

No RAG embeddings, compliance rules, models, loader, validation module, backend, or frontend code were created.

## 1. Executive Summary

The Day-0 repository scaffold is present and contains only `.gitkeep` placeholders under `code/` and `data/processed/`. No Python, FastAPI, frontend, model-training, or RAG application code exists.

The Day-0 baseline found 11 CSV files and recorded `05_progress.csv` as missing. At the Day-0.5 recheck, 12 CSV files are physically present, `05_progress.csv` contains the expected 14,902 rows, and all nine manifest-listed data files match their stated row counts. The two official supplemental files remain outside the manifest and data dictionary.

All tested canonical foreign-key relationships have 100% matches among non-null child keys. Primary IDs are unique and non-null. Important quality issues remain: 718 payment authorizations predate their requests; many records are future-dated relative to 2026-09-01; all 1,929 asset rows use the same completion date; 24 "Sanctioned - Not Started" works include 9 with nonzero progress, 10 with expenditure, and 10 with payment rows; one PFMS reference is duplicated; and the allocation file has one missing member amount.

The operational prototype tables are entirely synthetic (`synthetic_marker=True`). The two official files cannot be joined to the synthetic MP master by exact or normalized MP name: zero official rows match the 36 demo MPs. A controlled identity crosswalk is required before replacement or enrichment.

A naive `works LEFT JOIN payments` expands 3,000 work rows to 10,011 rows, `works LEFT JOIN progress` expands them to 15,172, and the actual naive three-table join expands them to 53,640 rows (17.88x). Payments and progress must remain separate DataFrames and be aggregated into a one-row-per-work feature table.

## 2. Environment Status

| Component | Status |
|---|---|
| Windows / OS | Registry reports Windows 10 Home Single Language, display version 25H2, build 26200.9168, x64. Runtime description: `Microsoft Windows 10.0.26200`. |
| Python | Not available on the host `PATH`. A Codex bundled runtime is available: Python 3.12.13 at `C:\Users\harsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. |
| pip | Not available independently on the host `PATH`; bundled Python has pip 26.2.1. |
| Node.js | Available: v26.5.0 at `C:\Program Files\nodejs\node.exe`. |
| npm | Available: 11.17.0 at `C:\Program Files\nodejs\npm.cmd`. |
| Git | Available: 2.55.0.windows.3 at `C:\Program Files\Git\cmd\git.exe`. |
| Docker | Not available on `PATH`. |
| Docker Compose | Not available because the Docker CLI is absent. |

Inspection-only libraries available in the bundled runtime include pandas 3.0.1, NumPy 2.3.5, pydantic 2.13.4, pypdf 6.10.0, and pdfplumber 0.11.9. No packages were installed.

## 3. Files Found

Important repository items found:

- `code/`: requested source scaffold; only `.gitkeep` files exist.
- `data/processed/`: generated-output target; currently only `.gitkeep`.
- `Demo-data/`: read-only source data; 12 CSV files physically present after the Day-0.5 update.
- `guidelines/official_mplads_guidelines.pdf`: 70-page MPLADS guidelines stating an effective date of 1 April 2023.
- `docs/reference/MPLADS_Sentinel_Revised_Master_Solution_Flow.pdf`: 15-page reference solution flow.
- `MASTER_CONTEXT.pdf`: 34-page build handoff and frozen-decision document.
- `architecture.drawio`: 19-page diagrams.net architecture source.
- `AGENTS.md`: repository governance and engineering instructions.
- `README.md`: concise project overview and data-design rules.
- `.gitignore`: Python, Node, secret, IDE/OS, model-artifact, and cache ignores; it does not ignore `Demo-data/` or `.env.example`.
- `.env.example`: safe placeholders for `ENVIRONMENT`, `XAI_API_KEY`, and `AS_OF_DATE`.
- `DAY_0_REPORT.md`: this report.

Day-0 correction: `Demo-data/05_progress.csv` now exists and passes the structural checks described in the Day-0.5 section.

## 4. CSV Schema Report

Row counts exclude the header. The two official supplemental files include a final `Grand Total` control row in their raw row counts. "Stored string/date" means pandas reads the value as text and the non-null detail values parse successfully as dates.

### `00_manifest.csv` - 9 rows x 3 columns

- Columns/inferred dtypes: `file_name:string`, `row_count:integer`, `purpose:string`.
- Likely primary key: `file_name` (9 unique, 0 null, 0 duplicates).
- Likely foreign keys: none; `file_name` is a logical reference to repository CSV paths.

### `01_mp_master.csv` - 36 rows x 15 columns

- Columns/inferred dtypes: `mp_id:string`, `mp_name:string`, `house_type:string/category`, `tenure:string`, `state_code:string`, `state_name:string/category`, `constituency:string`, `nodal_district:string`, `annual_entitlement_inr:integer`, `allocated_limit_inr:integer`, `calamity_consent_amount_inr:integer`, `record_effective_date:date (stored string)`, `source_type:string/category`, `source_reference:string`, `synthetic_marker:boolean`.
- Likely primary key: `mp_id` (36 unique, 0 null, 0 duplicates).
- Likely foreign keys: none inside this file. `mp_id` is referenced by `03_works.csv`.

### `02_agencies_vendors.csv` - 108 rows x 10 columns

- Columns/inferred dtypes: `entity_id:string`, `entity_type:string/category`, `entity_name:string`, `state_name:string/category`, `district:string/category`, `registration_or_office_code:string`, `vendor_category:string/category nullable`, `active_status:string/category`, `source_type:string/category`, `synthetic_marker:boolean`.
- Likely primary key: `entity_id` (108 unique, 0 null, 0 duplicates).
- Likely foreign keys: none inside this file. Agency entities are referenced by `03_works.implementing_agency_id` and `04_payments.authorized_by_agency_id`; vendor entities are referenced by `04_payments.vendor_id`.

### `03_works.csv` - 3,000 rows x 34 columns

- Columns/inferred dtypes: `work_id:string`, `mp_id:string`, `house_type:string/category`, `tenure:string`, `state_name:string/category`, `constituency:string`, `nodal_district:string`, `recommendation_date:date (stored string)`, `recommendation_type:string/category`, `sector:string/category`, `sub_sector:string/category`, `work_description:string`, `work_location_state:string/category`, `district:string/category`, `block:string/category`, `village:string/category`, `latitude:float`, `longitude:float`, `recommended_amount_inr:integer`, `technical_estimate_amount_inr:integer`, `sanctioned_amount_inr:integer`, `sanction_date:date (stored string, nullable)`, `sanction_status:string/category`, `implementing_agency_id:string nullable`, `expected_start_date:date (stored string, nullable)`, `expected_completion_date:date (stored string, nullable)`, `actual_start_date:date (stored string, nullable)`, `current_status:string/category`, `current_physical_progress_pct:float`, `current_expenditure_inr:integer`, `duplicate_group_reference:string nullable`, `source_type:string/category`, `source_reference:string`, `synthetic_marker:boolean`.
- Likely primary key: `work_id` (3,000 unique, 0 null, 0 duplicates).
- Likely foreign keys: `mp_id -> 01_mp_master.mp_id`; `implementing_agency_id -> 02_agencies_vendors.entity_id` restricted to `IMPLEMENTING_AGENCY`.

### `04_payments.csv` - 9,727 rows x 18 columns

- Columns/inferred dtypes: `payment_id:string`, `work_id:string`, `vendor_id:string`, `payment_request_date:date (stored string)`, `authorization_date:date (stored string)`, `payment_release_date:date (stored string)`, `payment_amount_inr:integer`, `payment_stage:string`, `invoice_number:string`, `cumulative_expenditure_inr:integer`, `payment_status:string/category`, `payment_mode:string/category`, `pfms_reference:string`, `authorized_by_agency_id:string`, `concurrence_authority:string`, `is_final_payment:boolean`, `source_type:string/category`, `synthetic_marker:boolean`.
- Likely primary key: `payment_id` (9,727 unique, 0 null, 0 duplicates).
- Likely foreign keys: `work_id -> 03_works.work_id`; `vendor_id -> 02_agencies_vendors.entity_id` restricted to `VENDOR`; `authorized_by_agency_id -> 02_agencies_vendors.entity_id` restricted to `IMPLEMENTING_AGENCY`.

### `06_assets_compliance.csv` - 1,929 rows x 20 columns

- Columns/inferred dtypes: `work_id:string`, `completion_date:date (stored string)`, `completion_marked_date:date (stored string)`, `final_expenditure_inr:integer`, `utilization_certificate_status:string/category`, `utilization_certificate_date:date (stored string, nullable)`, `asset_id:string`, `asset_type:string`, `user_agency:string`, `asset_register_entry:string/category`, `handover_date:date (stored string)`, `public_use_date:date (stored string)`, `audit_status:string/category`, `audit_date:date (stored string, nullable)`, `audit_observation_category:string/category`, `compliance_status:string/category`, `maintenance_agency:string`, `completion_photo_reference:string`, `source_type:string/category`, `synthetic_marker:boolean`.
- Likely primary keys: `work_id` and `asset_id` are each independently unique and non-null in the current data. This models one asset/closure row per completed work.
- Likely foreign key: `work_id -> 03_works.work_id`.

### `07_anomaly_ground_truth.csv` - 3,000 rows x 8 columns

- Columns/inferred dtypes: `work_id:string`, `injected_anomaly_count:integer`, `injected_anomaly_types:string`, `expected_risk_score_0_100:integer`, `expected_risk_class:string/category`, `duplicate_group_reference:string nullable`, `label_usage_note:string`, `synthetic_marker:boolean`.
- Likely primary key: `work_id` (3,000 unique, 0 null, 0 duplicates).
- Likely foreign key: `work_id -> 03_works.work_id`, for evaluation joins only.

### `08_data_dictionary.csv` - 120 rows x 6 columns

- Columns/inferred dtypes: `file_name:string/category`, `column_name:string`, `data_type:string/category`, `meaning:string`, `preferred_source_or_fallback:string`, `prototype_required:string/category`.
- Likely primary key: composite (`file_name`, `column_name`) (0 duplicate composite rows, 0 nulls).
- Likely foreign key: `file_name` logically references canonical dataset filenames.

### `09_source_acquisition_plan.csv` - 9 rows x 7 columns

- Columns/inferred dtypes: `priority:integer`, `dataset_or_field_group:string`, `target_file:string`, `preferred_source:string`, `acquisition_method:string`, `current_status:string`, `synthetic_fallback:string/category`.
- Likely primary key: `dataset_or_field_group` is unique in the current file; no formal ID exists.
- Likely foreign key: `target_file` is a logical, sometimes comma-separated reference to canonical files, not a normalized foreign key.

### `Allocated Limit for Honble MPs.csv` - 544 rows x 5 columns

- Composition: 543 MP detail rows plus one `Grand Total` row.
- Exact columns: `Sr. No.`, `State`, `Hon'ble Members of Parliaments`, `Constituency`, `Allocated AMOUNT ( ₹ )`.
- Raw dtypes: all strings because of the textual total row, comma-formatted grand total, and one missing amount. Semantic detail dtypes: serial number integer; state/member/constituency string; allocated amount nullable decimal INR.
- Likely primary key: `Sr. No.` is unique and non-null but is an export row number, not a durable domain identifier. MP name is unique within this snapshot but is not a safe stable key.
- Likely foreign key: member name/constituency could map to an authoritative MP identity table after normalization and crosswalk creation; there is no `mp_id`.

### `Amount consented for Calamity.csv` - 13 rows x 6 columns

- Composition: 12 consent-event detail rows plus one `Grand Total` row.
- Exact columns: `Sr. No.`, `Calamity Type`, `Calamity Name`, `Hon'ble Members of Parliament`, `Date of Consent`, `Consent Amount ( ₹ )`.
- Raw dtypes: all strings because of the total row and formatted total. Semantic detail dtypes: serial number integer; calamity type/name/member string; consent date date; consent amount integer INR.
- Likely primary key: `Sr. No.` is unique within the export but is not durable. MP name is not unique: 10 unique members across 12 event rows.
- Likely foreign key: normalized member identity could map to an authoritative MP master after a controlled crosswalk; there is no `mp_id` or constituency/state field.

### `05_progress.csv` - 14,902 rows x 15 columns (Day-0.5 verified)

- Columns/inferred dtypes: `progress_id:string`, `work_id:string`, `report_date:date (stored string)`, `physical_progress_pct:float`, `financial_progress_pct:float`, `expected_progress_pct_by_date:float`, `execution_stage:string/category`, `reported_status:string/category`, `reported_by_agency_id:string`, `photo_reference:string`, `geo_latitude:float`, `geo_longitude:float`, `remarks:string`, `source_type:string/category`, `synthetic_marker:boolean`.
- Likely primary key: `progress_id` (14,902 unique, 0 null, 0 duplicates).
- Likely foreign keys: `work_id -> 03_works.work_id`; `reported_by_agency_id -> 02_agencies_vendors.entity_id` restricted to `IMPLEMENTING_AGENCY`.
- Every column has 0 nulls. The exact 15-column name and order match the data dictionary.

## 5. Key Relationships

Actual-value checks produced the following results:

- All 36 distinct `works.mp_id` values occur in the MP master.
- All 36 distinct non-null `works.implementing_agency_id` values occur in the entity master and have `entity_type=IMPLEMENTING_AGENCY`.
- All 3,000 `work_id` values are unique in works.
- Payments reference 2,716 distinct works; every payment work exists in works.
- All 72 distinct `payments.vendor_id` values exist as `VENDOR` entities.
- All 36 distinct `payments.authorized_by_agency_id` values exist as `IMPLEMENTING_AGENCY` entities.
- Every asset/compliance work is a completed work, and the set of 1,929 asset work IDs exactly equals the set of 1,929 works marked `Completed`.
- All 3,000 evaluation-label work IDs exist in works.
- Progress contains 14,902 unique, non-null progress IDs over 2,730 works. Every work reference matches works, and every reporting-agency reference matches an `IMPLEMENTING_AGENCY` entity.

## 6. Relationship Integrity Results

Percentages below use non-null child keys as the denominator; the overall percentage is also shown where nulls exist.

| Relationship | Matched | Unmatched child IDs | Duplicate parent IDs | Null child keys |
|---|---:|---|---:|---:|
| `works.mp_id -> mp.mp_id` | 3,000/3,000 (100%) | None | 0 | 0 |
| `works.implementing_agency_id -> entities[IMPLEMENTING_AGENCY].entity_id` | 2,730/2,730 non-null (100%; 91.0% of all works) | None | 0 | 270 |
| `payments.work_id -> works.work_id` | 9,727/9,727 (100%) | None | 0 | 0 |
| `payments.vendor_id -> entities[VENDOR].entity_id` | 9,727/9,727 (100%) | None | 0 | 0 |
| `payments.authorized_by_agency_id -> entities[IMPLEMENTING_AGENCY].entity_id` | 9,727/9,727 (100%) | None | 0 | 0 |
| `assets.work_id -> works.work_id` | 1,929/1,929 (100%) | None | 0 | 0 |
| `ground_truth.work_id -> works.work_id` | 3,000/3,000 (100%) | None | 0 | 0 |
| `progress.work_id -> works.work_id` | 14,902/14,902 (100%) | None | 0 | 0 |
| `progress.reported_by_agency_id -> entities[IMPLEMENTING_AGENCY].entity_id` | 14,902/14,902 (100%) | None | 0 | 0 |

The 270 null implementing-agency keys align with 166 pending and 104 rejected works. They are conditional missingness, not orphaned IDs.

### Naive-merge multiplication check

- Base works: 3,000 rows.
- Payments: 9,727 rows covering 2,716 works; 2,299 works have multiple payments; maximum is 10 payments for one work.
- `works LEFT JOIN payments` result: 10,011 rows, or 3.337 times the work table.
- Calculation: 9,727 payment-bearing joined rows plus 284 works with no payment equals 10,011.
- `works LEFT JOIN progress` result: 15,172 rows.
- Actual naive `works LEFT JOIN payments LEFT JOIN progress` result: 53,640 rows, or 17.88 times the work table. For each work, the join creates `max(1, payment_count) * max(1, progress_count)` rows and repeats monetary/progress facts.
- The correct design is separate `df_mp`, `df_entities`, `df_works`, `df_payments`, `df_progress`, and `df_assets` DataFrames plus an aggregated `df_project_features` with exactly one row per work.

## 7. Missingness / Data Quality Findings

### Missing values

- MP master: no nulls.
- Entity master: `vendor_category` has 36 nulls, exactly the 36 implementing-agency rows where a vendor category is not applicable.
- Works: 270 nulls each in `sanction_date`, `implementing_agency_id`, `expected_start_date`, `expected_completion_date`, and `actual_start_date`; these correspond to pending/rejected works. `duplicate_group_reference` has 2,910 nulls and is an optional synthetic evaluation helper.
- Payments: no nulls.
- Progress: no nulls in any of its 15 columns.
- Assets/compliance: 39 null `utilization_certificate_date` values and 1,282 null `audit_date` values. The status counts explain most of these: 39 UC records are pending/not submitted, and only 647 audits are marked completed.
- Ground truth: 2,910 null `duplicate_group_reference` values; other fields have no nulls.
- Allocation export: one missing amount for row 108, `CHAVAN VASANTRAO BALWANTRAO`, constituency `NANDED`.
- Calamity export: no missing detail values.

### Dates and chronology

- All non-null canonical date strings parse successfully; no malformed non-null canonical dates were found.
- There are 718 payment rows where `authorization_date < payment_request_date`, an impossible workflow chronology that needs validation/rejection or correction.
- No payment release precedes its authorization. No work sanction precedes recommendation. No expected completion precedes expected start.
- Relative to the inspection date 2026-09-01, future operational dates exist: 4 actual work starts, 42 payment requests, 50 payment authorizations, and 55 payment releases.
- Asset/closure future dates are extensive: 1,597 completion-marked dates, 1,890 non-null UC dates, 1,828 handover dates, 1,874 public-use dates, and all 647 non-null audit dates occur after 2026-09-01.
- Future expected completion dates (547) are not inherently invalid because they are plans. Future actual starts or released payments are inconsistent for an as-of dataset unless the dataset intentionally represents a future simulation.
- Every one of the 1,929 asset rows has the identical `completion_date=2026-08-31`, an obvious synthetic artifact that is unsuitable as real completion history.
- Progress report dates have no malformed, null, or future values relative to 2026-09-01. None precede recommendation or sanction, and none follow recorded completion. Twelve reports across five works precede the recorded actual start date; classify these as lifecycle inconsistencies needing interpretation, not as fraud.

### Percentages and coordinates

- `works.current_physical_progress_pct` ranges from 0 to 100 with 0 values below 0, 0 values above 100, and 0 nulls.
- Progress physical and expected percentages stay within 0-100 with no null/non-numeric values. Financial progress ranges from 0 to 164.1 and has 4,292 values above 100; this needs later business-rule interpretation and may reflect the synthetic expenditure-over-sanction scenarios.
- Ground-truth risk scores remain within 0-100.
- All latitude/longitude values are within global coordinate bounds and all 3,000 coordinate pairs are distinct. Plausibility against actual work locations was not externally geocoded on Day 0.

### Monetary values and cross-field consistency

- No negative values were found in MP allocations, work amounts, payments, cumulative expenditure, or final expenditure.
- Four payment rows have amount zero; all belong to `W-002267` and are marked `Released`. Zero-value released transactions require special handling.
- 1,215 works have current expenditure above sanctioned amount; 1,612 have sanction above technical estimate; 1,284 have technical estimate below recommended amount. These can be deliberate anomaly injections, but they are business-rule flags and must not be silently normalized.
- Payment cumulative expenditure exactly equals calculated per-work cumulative sums for all 9,727 rows.
- For all 2,716 works with payments, summed payments exactly equal `works.current_expenditure_inr`; asset final expenditure also equals the current work expenditure for all 1,929 assets.
- The allocation detail sum equals its grand total (`INR 83,180,553,325.71`) despite one missing member amount, indicating the published grand total cannot be reconstructed solely from the visible non-null member amounts unless the missing amount is effectively embedded elsewhere or the export total reflects an upstream value.
- The calamity detail sum exactly equals its grand total (`INR 40,567,400`).

### Stale and inconsistent records

- All operational rows in MP, entity, works, payments, and assets tables are marked synthetic. They are not live government records.
- Six Rajya Sabha MP rows still carry the tenure text `18th Lok Sabha / Current Demo Tenure`, a semantic mismatch.
- Of 24 works labelled `Sanctioned - Not Started`, 9 have nonzero physical progress, 10 have nonzero expenditure, and 10 have payment rows.
- Four works have future `actual_start_date`; one is already `Ongoing`, while others are `Sanctioned - Not Started`.
- The operational tables generally lack ingestion timestamps/source snapshot timestamps, so true source freshness cannot be measured.
- The official allocation/calamity exports exist, but the synthetic MP master has not incorporated them.
- Physical progress decreases across 295 consecutive-report transitions affecting 220 works; the largest decrease is 12.8 percentage points. These may be revised reporting, data errors, legitimate corrections, or synthetic anomalies and were not modified.

## 8. Duplicate / Key Integrity Findings

- No duplicate or null values exist in the likely primary keys: `mp_id`, `entity_id`, `work_id`, `payment_id`, `asset_id`, or ground-truth `work_id`.
- `invoice_number` is unique and non-null.
- `progress_id` is unique and non-null. There are 13 same-work/same-report-date duplicate extras, but their progress IDs are distinct.
- One duplicate PFMS reference exists: `DEMO-PFMS-65604569` is shared by payments `P-W-000764-02` and `P-W-001165-05` on different works.
- Works contain 90 non-null duplicate-group references across 47 groups. Group sizes are: 19 singleton groups, 19 groups of two, 7 groups of three, and 2 groups of six. Singleton "duplicate" groups are internally inconsistent and should not be treated as duplicate pairs without review.
- Work descriptions have 23 duplicate extras (45 rows involved), but no entire business record is an exact duplicate when IDs/helper/metadata fields are excluded.
- The allocation file has unique member names but duplicated constituency `NANDED` for two Maharashtra MPs; constituency is therefore not a key.
- The calamity file correctly contains repeat members because one member can consent to multiple calamity events.

## 9. Official Allocation CSV Analysis

`Allocated Limit for Honble MPs.csv` contains 543 detail records and one total row. Its schema is documented in Section 4.

- Identifiers: export serial number, MP display name, state, and constituency. It lacks a stable `mp_id`, house type, tenure, nodal district, and effective date.
- Join feasibility: zero of 543 detail records match `01_mp_master.mp_name`, even after case, punctuation, Unicode, and common honorific normalization. All 543 official records and all 36 synthetic master rows remain unmatched by name.
- State-only matching is unsafe: 165 official rows belong to the six states represented in the synthetic master, but a state join would be many-to-many and could assign values to the wrong MP.
- Replacement/enrichment potential: authoritative `mp_name`, `state_name`, `constituency`, and `allocated_limit_inr`. It cannot directly replace the synthetic `mp_id`, `house_type`, `tenure`, `nodal_district`, `annual_entitlement_inr`, provenance, or effective-date fields.
- Required bridge: a reviewed MP identity crosswalk using authoritative MP/house/term identifiers. Names alone are insufficient.
- Quality findings: one member amount is missing at serial 108; `NANDED` appears twice; the detail names and serial numbers are otherwise unique; the numeric detail sum matches the provided grand total.

No source data was changed or merged.

## 10. Calamity Consent CSV Analysis

`Amount consented for Calamity.csv` contains 12 event records and one total row. Its schema is documented in Section 4.

- Identifiers: export serial number, MP display name, calamity type/name, and consent date. It lacks `mp_id`, state, constituency, house, and tenure.
- Join feasibility: zero of 12 event rows match `01_mp_master.mp_name`, even after normalization. The 12 unmatched events represent 10 unique official MP names; all 36 synthetic master MPs are unmatched.
- Repeat members are valid event cardinality: `SHAFI PARAMBIL` and `Shri NK Premachandran` each have two events.
- Replacement/enrichment potential: consent event type, name, date, and amount. The scalar master field `calamity_consent_amount_inr` would require a documented aggregation rule, such as sum by MP and effective period. Preserving an event-level calamity table would retain more information.
- Required bridge: a reviewed authoritative MP identity crosswalk. The absence of state/constituency makes name-only resolution especially risky.
- Quality findings: all 12 detail dates parse, amounts are non-negative, serial numbers are unique, and the detail sum matches the `INR 40,567,400` grand total.

No source data was changed or merged.

## 11. Manifest Verification

| Manifest file | Stated rows | Actual rows | Result |
|---|---:|---:|---|
| `01_mp_master.csv` | 36 | 36 | Match |
| `02_agencies_vendors.csv` | 108 | 108 | Match |
| `03_works.csv` | 3,000 | 3,000 | Match |
| `04_payments.csv` | 9,727 | 9,727 | Match |
| `05_progress.csv` | 14,902 | 14,902 | Match |
| `06_assets_compliance.csv` | 1,929 | 1,929 | Match |
| `07_anomaly_ground_truth.csv` | 3,000 | 3,000 | Match |
| `08_data_dictionary.csv` | 120 | 120 | Match |
| `09_source_acquisition_plan.csv` | 9 | 9 | Match |

All nine manifest row counts now match the physical canonical files. The manifest correctly labels ground truth as validation-only. It does not list itself or the two supplemental official CSVs.

## 12. Data Dictionary Verification

- The dictionary has 120 rows and no duplicate (`file_name`, `column_name`) pairs.
- For every present canonical table, documented and observed column names and order match exactly:
  - MP master: 15/15.
  - Agency/vendor master: 10/10.
  - Works: 34/34.
  - Payments: 18/18.
  - Progress: 15/15.
  - Assets/compliance: 20/20.
  - Ground truth: 8/8.
- The dictionary's 15 progress fields, order, meanings, and logical types match the observed file. `report_date` is stored as text in CSV but all values parse as dates; numeric and boolean fields load with compatible types.
- Documented logical types are compatible with observed values in present canonical tables. CSV parsers read dates/categories as strings by default; all tested non-null date values parse, and integer/float/boolean fields load as expected.
- The dictionary does not document `00_manifest.csv`, itself, `09_source_acquisition_plan.csv`, or either official supplemental CSV. The last two official files therefore have no canonical mapping rules in the dictionary.

## 13. Source Acquisition Status

The source plan contains nine priorities:

| Field group | Preferred official source | Current status / fallback |
|---|---|---|
| MP allocation limits | MoSPI supplied allocation export | Official file supplied but not integrated; synthetic fallback currently used. |
| Calamity consent amounts | MoSPI supplied calamity export | Official file supplied but not integrated; synthetic fallback currently used. |
| Work recommendations/descriptions | Official MPLADS/eSAKSHI reports | Public records confirmed; automated eSAKSHI scraping blocked by human verification; synthetic fallback. |
| Sanctions/amounts/dates | eSAKSHI/MPLADS reports | Partly public; exact extractability still needs testing; synthetic fallback. |
| Expenditure | Public expenditure reports/eSAKSHI | Aggregate/work expenditure appears public; transaction-level access uncertain; synthetic payment detail. |
| Physical progress history | eSAKSHI | Synthetic prototype file is now present and structurally valid; an official bulk replacement remains unavailable. |
| Vendor payment transactions | eSAKSHI/PFMS/CNA | Detailed public/authorized access uncertain; synthetic fallback. |
| Asset/completion/UC/audit | eSAKSHI and public documents | Completion public; detailed UC/audit fields may be limited; synthetic fallback. |
| Known anomaly/fraud labels | Legally public audit/investigation findings | No clean labels expected; controlled synthetic anomalies are for validation only. |

Production-readiness limitations: operational records, including progress, are synthetic; official files lack stable project MP IDs; official progress and payment/vendor/PFMS detail may be restricted; provenance and snapshot timestamps are incomplete; and source permissions/acquisition methods require confirmation before automation.

## 14. Ground Truth Isolation Check

`07_anomaly_ground_truth.csv` is evaluation/validation-only. Its own `label_usage_note` says not to expose it as a production model input, the manifest says never to use it as model input, and `MASTER_CONTEXT.pdf` repeats the leakage prohibition.

The following columns must never be production/model features: `injected_anomaly_count`, `injected_anomaly_types`, `expected_risk_score_0_100`, `expected_risk_class`, `duplicate_group_reference` when sourced from ground truth, `label_usage_note`, and any derived transformation of these fields. `work_id` may be used only to align predictions with labels during isolated evaluation.

Repository verification found no `.py`, `.js`, `.ts`, frontend, backend, or other application source files under `code/`. A recursive search found no references to the ground-truth filename or its label columns. Therefore no code currently imports this file into a feature matrix. This rule must remain enforced in Day 1 and later.

## 15. Guideline PDF Extraction Check

File: `guidelines/official_mplads_guidelines.pdf`.

- Exact size: 1,642,098 bytes.
- Page count: 70; 64 pages contain extracted text.
- Extractable title: `MEMBERS OF PARLIAMENT LOCAL AREA DEVELOPMENT SCHEME Guidelines`.
- Document-stated dates: cover date `APRIL 1, 2023`; first edition 22 February 2023; second edition 14 March 2023; clause 1.1 says it comes into force from 1 April 2023 and supersedes previous MPLADS guidelines and instructions.
- PDF metadata records creation in November 2025, but the text does not identify a 2025 edition. Metadata is not treated as a revision claim.
- Normal extraction works with pypdf: approximately 109,659 characters, including whitespace, and 92,141 non-whitespace characters.
- Headings and annexures: Chapters 1-11 and Annexures I-VIII are extractable and usable for later section-based chunking.
- OCR: not used and not necessary.
- Visual spot check: the cover renders cleanly and displays the title and 1 April 2023 date.
- Later RAG suitability: technically suitable after cleaning repeated headers/footers and retaining page, chapter, edition, and source metadata. RAG was not built.
- Governance warning: the file is clearly newer than the former 2005 document and states that it supersedes earlier guidelines. Currentness still requires authoritative verification before production compliance rules or RAG.

## 16. Architecture / Context Consistency

What aligns:

- `architecture.drawio` contains 19 pages, and their names match the exact 19-page list in `MASTER_CONTEXT.pdf` (the Draw.io file uses an em dash in the Grok page title while the PDF uses a hyphen; this is cosmetic).
- Both describe lifecycle-separated MP, work, payment, progress, and asset data; a trusted foundation; feature construction; stage-aware intelligence; explainable risk fusion; grounded guideline explanation; role-based delivery; and human verification.
- Both state that ground-truth labels are for benchmarking/evaluation and must be excluded from features.
- Both position Grok as grounded explanation rather than the core anomaly detector.

Obvious inconsistencies or stale assumptions:

- The Draw.io implementation labels still specify PostgreSQL/PostGIS, object storage, MLflow, worker queues, PostgreSQL audit tables, and related infrastructure. `MASTER_CONTEXT.pdf` freezes the MVP as CSV-first/in-memory and explicitly says not to reintroduce PostgreSQL/SQL unless the decision changes. The architecture diagram is conceptually aligned but its implementation-stack annotations are stale.
- Both architecture/context assume `05_progress.csv` exists; the Day-0.5 input now satisfies that assumption structurally.
- The master context says the exact headers/rows of the two official supplemental files had not yet been inspected. This report has now inspected them, so that statement is stale.
- Both documents present FastAPI/Next.js and Grok/RAG as later architecture components. None are currently implemented, which is consistent with Day 0.
- The guideline artifact has been replaced by the document-stated 2023 edition. It is newer than the Day-0 file, but authoritative currentness remains unresolved.

No architecture was redesigned or modified.

## 17. Current Repository Structure

```text
C:\SIH-PROJECT
|-- .env.example
|-- .gitignore
|-- AGENTS.md
|-- DAY_0_REPORT.md
|-- MASTER_CONTEXT.pdf
|-- README.md
|-- architecture.drawio
|-- code
|   |-- intelligence
|   |   |-- data\
|   |   |-- features\
|   |   |-- anomaly\
|   |   |-- payments\
|   |   |-- delay\
|   |   |-- overrun\
|   |   |-- duplicates\
|   |   |-- compliance\
|   |   |-- completion\
|   |   |-- trends\
|   |   `-- risk_fusion\
|   |-- rag\
|   |-- backend\
|   |-- frontend\
|   |-- models\
|   `-- tests\
|       (each leaf directory contains only .gitkeep)
|-- data
|   `-- processed
|       `-- .gitkeep
|-- Demo-data
|   |-- 00_manifest.csv
|   |-- 01_mp_master.csv
|   |-- 02_agencies_vendors.csv
|   |-- 03_works.csv
|   |-- 04_payments.csv
|   |-- 05_progress.csv
|   |-- 06_assets_compliance.csv
|   |-- 07_anomaly_ground_truth.csv
|   |-- 08_data_dictionary.csv
|   |-- 09_source_acquisition_plan.csv
|   |-- Allocated Limit for Honble MPs.csv
|   `-- Amount consented for Calamity.csv
|-- docs
|   `-- reference
|       `-- MPLADS_Sentinel_Revised_Master_Solution_Flow.pdf
`-- guidelines
    `-- official_mplads_guidelines.pdf
```

`05_progress.csv` is present in the physical tree as of the Day-0.5 recheck.

## 18. Missing Dependencies

No repository dependency manifest exists (`requirements.txt`, `pyproject.toml`, lockfile, `package.json`, Dockerfile, or Compose file).

Environment/dependency gaps for later work:

- Host Python and pip are not on `PATH`; Day 1 needs a deliberate project Python environment rather than relying on the Codex inspection runtime.
- Docker and Docker Compose are unavailable.
- Schema/column validation packages such as `pandera` are absent.
- `pyarrow` is absent if Parquet/interchange support is later chosen.
- ML stack packages are absent: scikit-learn, SciPy, joblib, SHAP.
- Duplicate/text stack packages are absent: RapidFuzz, sentence-transformers, FAISS.
- Backend/test packages are absent: FastAPI, Uvicorn, HTTPX, pytest.
- Node/npm are installed, but no frontend project or `package.json` exists.

These are observations, not installation instructions. Dependency status is unchanged at Day 0.5, and no dependencies were installed.

## 19. Risks / Blockers

- Progress quality: 4,292 financial-progress values exceed 100, 295 physical-progress decreases affect 220 works, 12 reports precede recorded actual starts, and 13 same-work/same-date duplicate extras need validation policy. The missing-file blocker is resolved.
- ML training: all operational records are synthetic; future-dated rows can leak simulated future information; no production labels exist; ground truth must remain isolated.
- Duplicate detection: helper groups include 19 singleton groups; exact description duplicates are not exact full-record duplicates; later evaluation needs a clear pair/group protocol.
- Compliance checks: the replacement guideline states a 2023 second edition/effective date and supersession of earlier guidance, but currentness still requires authoritative verification before encoding production rules.
- Allocation/calamity integration: official exports lack `mp_id`; exact/normalized name joins to the synthetic master produce zero matches; a governed crosswalk is required.
- Payment quality: 718 reversed request/authorization chronologies, one duplicate PFMS reference, four zero-value released payments, and future releases require validation handling.
- Temporal validity: widespread future-dated asset/closure records and one shared completion date can distort delay/completion models.
- RAG: extraction is feasible and the updated chapters/annexures are usable, but source acceptance, currentness verification, cleanup, and version metadata remain required before indexing.
- Frontend/backend integration: no API contract implementation, dependency manifest, frontend project, backend project, container runtime, or application tests exist yet.
- Architecture drift: Draw.io stack annotations conflict with the frozen CSV-first/no-SQL MVP decision in the master context.
- Row multiplication: raw joins across one-to-many payment and progress histories would corrupt sums and counts. Separate DataFrames and one-row-per-work aggregations are mandatory.

## 20. Recommended Next Development Step

**Day 1 - CSV Data Loader + Validation**

After explicit approval, Day 1 should load each source into a separate DataFrame, validate file presence and exact schemas, parse dates/numerics explicitly, enforce key and relationship checks, use an explicit `AS_OF_DATE` rather than blindly depending on the system clock, produce non-destructive validation outputs under `data/processed/`, and keep `07_anomaly_ground_truth.csv` outside every production/feature-loading path. Payments and progress must remain separate one-to-many tables.

Day 1 has not been started by this report.

## Appendix A - Commands Used for Day-0 Inspection

The following commands/tools were used read-only except for creating this Markdown report and temporary PDF page images for visual inspection:

```powershell
Get-ChildItem -LiteralPath C:\SIH-PROJECT -Force
rg --files C:\SIH-PROJECT
Get-FileHash -Algorithm SHA256 C:\SIH-PROJECT\Demo-data\<file>.csv
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
Get-Command python,pip,node,npm.cmd,git,docker,pdfinfo
node --version
npm.cmd --version
git --version
docker --version
docker compose version
C:\Users\harsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe --version
C:\Users\harsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pip --version
C:\Users\harsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -
Get-Content -LiteralPath C:\SIH-PROJECT\architecture.drawio
rg -n --hidden '07_anomaly_ground_truth|anomaly_ground_truth|injected_anomaly|expected_risk_score_0_100|expected_risk_class' C:\SIH-PROJECT\code
pdftoppm.exe -f 1 -l 1 -singlefile -png -r 120 <PDF> <temporary-output-prefix>
tree.com C:\SIH-PROJECT /F /A
```

The inline bundled-Python inspections used pandas for CSV schema/row/dtype/null/key/relationship/date/percentage/money/duplicate/join analysis, pypdf for PDF page/text extraction, and Python XML parsing for Draw.io page names and labels. No network calls, Grok calls, package installations, application generators, training commands, or data writes were performed.

## Appendix B - Source Integrity and Stop Condition

At Day 0.5, all 12 physically present `Demo-data` files, including the new `05_progress.csv`, were fingerprinted by filename, byte length, and SHA-256 before inspection. The same fingerprint is rechecked after documentation updates. `Demo-data` is treated as immutable and read-only.

`07_anomaly_ground_truth.csv` remains evaluation-only. No production feature matrix or import path exists.

This report completes Day 0 and the Day-0.5 recheck only. Stop here and wait for explicit approval before Day 1.
