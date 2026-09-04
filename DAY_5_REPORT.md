# DAY 5 REPORT - MPLADS Compliance Rule Engine + Guideline Evidence Foundation

Execution date: 2026-09-02  
Project root: `C:\SIH-PROJECT`  
Controlled snapshot: `AS_OF_DATE=2026-09-01`

# 1. Day 5 Goal

Day 5 implemented only a verified/versioned guideline foundation, deterministic
lifecycle-aware compliance rules, clause-linked evidence, a one-row-per-work
summary, a transparent implemented/deferred registry, local text chunks for later
retrieval, and regression tests.

It did not implement an LLM decision path, embeddings, RAG answers, final risk
fusion, predictive delay or overrun models, SHAP, an API, a frontend, an officer
workflow, automatic escalation, self-learning, or Day 6.

# 2. Guideline Verification

The official MPLADS portal currently lists **English Guidelines 2023** and links
to:

`https://www.mplads.gov.in/MPLADS/UploadedFiles/MPLADSGuidelines2023_English_.pdf`

The local PDF identifies itself as **Members of Parliament Local Area Development
Scheme Guidelines**, records the First Edition dated 22 February 2023 and Second
Edition dated 14 March 2023, and states in Clause 1.1 that it came into force on
1 April 2023. These details agree with the official portal and MoSPI's published
description of the revised guideline.

The local cover, editions page, and representative rule pages were rendered and
visually inspected in addition to deterministic text extraction. No material
identity, edition, or effective-date discrepancy was found.

Directly downloading a second server copy for byte-level comparison timed out on
the official host. The verification therefore does not claim an official-server
checksum. It records the local file's checksum and distinguishes that from the
official identity/edition verification.

# 3. Guideline Version / Manifest

| Field | Recorded value |
|---|---|
| Document | Members of Parliament Local Area Development Scheme Guidelines |
| Version | MPLADS Guidelines 2023 - Second Edition, 14 March 2023 |
| Effective date | 2023-04-01 |
| Local file | `guidelines/official_mplads_guidelines.pdf` |
| Local SHA-256 | `2E4AF29D2FAAADBA4E8DADB16C30D56318AF23CD062436260ACA11777CEBC5E6` |
| Total PDF pages | 70 |
| Pages with extractable text | 64 |
| Verification date | 2026-09-02 |
| Extraction | PyMuPDF 1.28.2, normal text extraction, no OCR |
| Extracted characters | 125,024 |
| Stable chunks | 61 |

The PDF metadata contains a 17 November 2025 creation timestamp from PDFium. It
is explicitly recorded as file metadata and is not treated as an edition date.

# 4. Dependencies

Only `PyMuPDF>=1.24,<2` was added to `pyproject.toml` and the project Python 3.12
environment. The resolved version is PyMuPDF 1.28.2. It is used for local text
extraction and page metadata only.

No embedding, vector-database, external model, web-framework, frontend, or future
predictive-model dependency was added.

# 5. Files Created / Modified

Created source files:

- `code/intelligence/compliance/__init__.py`
- `code/intelligence/compliance/models.py`
- `code/intelligence/compliance/guideline.py`
- `code/intelligence/compliance/rules.py`
- `code/intelligence/compliance/rule_registry.py`
- `code/intelligence/compliance/engine.py`
- `code/intelligence/compliance/runner.py`
- `code/tests/test_compliance.py`
- `DAY_5_REPORT.md`

Created generated artifacts under `data/processed`:

- `compliance_evidence.csv`
- `compliance_summary.csv`
- `compliance_rule_registry.json`
- `guideline_chunks.json`
- `guideline_manifest.json`
- `day5_compliance_summary.json`

Modified:

- `pyproject.toml` - declared PyMuPDF.
- `AGENTS.md` - added guideline currentness, versioning, and deterministic-decision
  guardrails.
- `README.md` - added Day-5 status and runner command.

The obsolete compliance `.gitkeep` marker was removed when the package was
created. No prior generated artifact was rewritten.

# 6. Compliance Governance

The engine permits only:

- `PASS`
- `REVIEW`
- `NON_COMPLIANT`
- `NOT_APPLICABLE`
- `INSUFFICIENT_DATA`

`NON_COMPLIANT` is emitted only when available fields directly contradict a clear
clause without contextual judgment. Qualifying language and missing context lead
to `REVIEW` or `INSUFFICIENT_DATA`. A future event is not treated as completed at
the 2026-09-01 snapshot, and a lifecycle-specific obligation is not applied to an
earlier lifecycle.

Severity (`INFO`, `WARNING`, or `STRONG_WARNING`) expresses review importance,
not guilt or a final risk class. Counts remain evidence counts; they are not fused
or converted into a risk score.

# 7. Rule Registry Design

Each implemented rule records its ID, title, category, description, lifecycle
applicability, review severity, guideline version, chapter, clause, physical PDF
page, printed page, chunk IDs, official reference, required fields, explicit
evaluation logic, result semantics, and a test identifier.

Deferred entries use `UNIMPLEMENTED_RULE_CANDIDATE` and record the precise missing
field or context. The registry contains eight implemented rules and nine deferred
candidates. Rule IDs and chunk IDs are unique, and every implemented clause and
chunk reference is resolved during the runner and tests.

# 8. Implemented Rules

| Rule ID | Clause | Purpose | PASS | REVIEW | NON_COMPLIANT | NOT_APPLICABLE | INSUFFICIENT_DATA |
|---|---|---|---:|---:|---:|---:|---:|
| `MPLADS-3.2.4-SANCTION-45D` | 3.2.4, 3.2.6 | Check recommendation response within 45 days, while respecting unavailable model-code exclusions | 2,418 | 312 | 0 | 270 | 0 |
| `MPLADS-3.2.9-MIN-SANCTION` | 3.2.9 | Check the normal INR 2.5 lakh minimum while preserving the reasoned exception | 2,730 | 0 | 0 | 270 | 0 |
| `MPLADS-3.2.12-COMPLETION-LIMIT` | 3.2.12 | Check the general one-year sanction-letter completion band | 2,355 | 375 | 0 | 270 | 0 |
| `MPLADS-3.2.17-PUBLIC-USE` | 3.2.17 | Check for public-use evidence after completion | 55 | 1,874 | 0 | 1,071 | 0 |
| `MPLADS-4.5.3-COMPLETION-PHOTO` | 4.5.3 | Check for a completed-work photograph reference | 1,929 | 0 | 0 | 1,071 | 0 |
| `MPLADS-11.3-ASSET-HANDOVER` | 11.3 | Check for visible transfer to the User Agency | 101 | 1,828 | 0 | 1,071 | 0 |
| `MPLADS-4.5.8-ASSET-REGISTER` | 4.5.8, 11.3 | Check register entry only after visible handover | 99 | 1 | 1 | 2,899 | 0 |
| `MPLADS-11.2-COMPLETION-UC` | 11.2 | Check for visible submitted-certificate evidence after completion | 0 | 1,929 | 0 | 1,071 | 0 |

The 45-day, minimum-amount, and one-year checks do not convert exception-capable
clauses into automatic violations. Public use, handover, and completion UC also
use `REVIEW` when evidence is not visible because the clauses do not provide a
numeric grace period testable from these work rows.

# 9. Unimplemented Rule Candidates

| Candidate | Clause | Missing data or context |
|---|---|---|
| Full estimate consent/allocation | 3.2.3 | MP consent and full allocation evidence |
| O&M undertaking before sanction | 3.2.7 | Written User Agency undertaking |
| Statutory clearances before sanction | 3.2.8 | Applicable clearance types and dated documents |
| Open and transparent bidding | 3.2.13 | Tender publication, bid, and evaluation records |
| Annual district inspection coverage | 4.5.2 | District-year work denominator and inspection register |
| Implementing Agency inspection coverage | 4.6.2 | Work-site visit/inspection register |
| Durable public asset and unrestricted access | 5.1.1, 5.1.2 | Land ownership, institutional control, durability, and access restrictions |
| UC linked to each vendor payment | 11.4.1 | Payment-to-certificate linkage |
| Annual audit report deadline | 11.4.4 | Fund-release financial year and authority-level audit report date |

No description-only classifier or invented assumption was used to fill these
gaps.

# 10. Lifecycle Applicability

Sanction rules apply only to `EXECUTION` and `COMPLETION`. Completion, public-use,
handover, register, photo, and UC rules apply only to `COMPLETION`. Other stages
receive `NOT_APPLICABLE`, not a failure.

The asset-register rule has an additional due-point guard: it is not applicable
until a handover date is visible by the snapshot. Asset rows are grouped by work,
so the engine remains capable of evaluating multiple real asset records per work.

# 11. Compliance Findings

Across 24,000 work-rule rows:

| Result | Count |
|---|---:|
| PASS | 9,687 |
| REVIEW | 6,319 |
| NON_COMPLIANT | 1 |
| NOT_APPLICABLE | 7,993 |
| INSUFFICIENT_DATA | 0 |

- 2,132 works have at least one `REVIEW` result.
- One work has deterministic `NON_COMPLIANT` evidence.
- Zero current works have `INSUFFICIENT_DATA` results under the eight implemented
  rules; missing-data branches remain tested for future inputs.

The single deterministic result is `W-000933`: handover is visible by the
snapshot, while the source explicitly records `asset_register_entry=No`.
`W-000706` has a visible handover and a pending register entry, so it correctly
receives `REVIEW` instead.

The large review count is expected: most synthetic closure events occur after the
controlled snapshot, and clauses such as “quickly” and “without delay” do not
support invented numeric deadlines. The count is not a risk score.

# 12. Guideline Extraction

PyMuPDF normal text extraction succeeds without OCR. It returns text on 64 of 70
PDF pages and 125,024 raw characters. The text preserves chapter headings, clause
numbers, annexure labels, and enough page structure for deterministic lookup.

Six pages have no extractable text. Three additional extractable pages contain
only repeated header/page material after cleanup, leaving 61 content-bearing
chunks. OCR was not used because the substantive document text is directly
extractable.

# 13. Guideline Chunk Foundation

`guideline_chunks.json` contains 61 stable page-aligned chunks. Each includes:

- deterministic `chunk_id` such as `MPLADS-2023-P020`;
- guideline version;
- physical PDF page range and printed page where detectable;
- carried-forward chapter;
- identified clause numbers;
- cleaned local text; and
- the source PDF SHA-256.

Page alignment preserves auditability and avoids arbitrary tiny fragments. No
embedding or semantic retrieval index was created on Day 5.

# 14. Clause-to-Evidence Traceability

Every evidence row carries the version, chapter, clause, physical and printed
page, chunk IDs, and official source reference. For example, the one-year planning
check resolves Clause 3.2.12 to `MPLADS-2023-P020`; the handover and UC rules
resolve to `MPLADS-2023-P051`.

`get_guideline_chunk(chunk_id)` performs exact chunk lookup, while
`get_guideline_clause(reference)` resolves clause-number starts in extracted text.
The runner refuses to produce compliance output if an implemented rule's clause
or chunk cannot be resolved.

# 15. Outputs

| Artifact | Size / rows | Purpose |
|---|---:|---|
| `compliance_evidence.csv` | 24,000 rows | explainable work-rule evidence |
| `compliance_summary.csv` | 3,000 unique works | per-work status counts and top actionable rule |
| `compliance_rule_registry.json` | 8 implemented + 9 deferred | versioned rule audit trail |
| `guideline_manifest.json` | 1 manifest | verified identity, hash, extraction/version record |
| `guideline_chunks.json` | 61 chunks | deterministic future retrieval foundation |
| `day5_compliance_summary.json` | 1 summary | rule/category counts, work counts, paths, governance |

No output contains a final risk score or class.

# 16. Tests

Every implemented rule has synthetic PASS, REVIEW or direct-contradiction,
NOT_APPLICABLE, and INSUFFICIENT_DATA coverage as relevant. Global coverage also
checks:

- exactly 3,000 unique summary work IDs;
- the five-value result vocabulary;
- clause/page/reference completeness and clause/chunk resolution;
- PDF page count and local hash;
- source-page bounds;
- AS_OF_DATE handling for future public-use, handover, and UC events;
- absence of external decision-service calls and prohibited helper inputs;
- production-language safeguards;
- all frozen prior artifacts; and
- all 12 Demo-data hashes.

Command:

```powershell
$env:AS_OF_DATE = '2026-09-01'
C:\SIH-PROJECT\.venv\Scripts\python.exe -m pytest
```

Final result on Python 3.12.10: **79 passed in 9.94 seconds**.

# 17. Source / Prior-Artifact Integrity

Post-test verification checked 15 frozen Day-2 through Day-4 artifacts with zero
mismatches, including project features, anomaly scores and models, peer summary,
duplicate embeddings/candidates/summary/metadata, payment outputs, fund-progress
output, and the Day-4 summary.

The full test suite also revalidated all 12 `Demo-data` CSV hashes. No source CSV
was modified, renamed, moved, deleted, or overwritten. The duplicate formula and
review policy, payment evidence, fund-progress evidence, and Day-3 models remain
unchanged.

# 18. Limitations

- The dataset is synthetic and has a single controlled snapshot without ingestion
  timestamps.
- The official host timed out during an attempted second PDF download, so the
  manifest records a local checksum rather than claiming an official-server hash.
- Many completion records are only one day old at the snapshot, while future
  source closure dates are deliberately masked; review counts therefore reflect
  snapshot context as well as administrative evidence.
- No exact grace period was invented for “quickly,” “without delay,” or “as soon
  as” language.
- Current work-level UC and audit fields cannot prove payment-level certificate or
  authority-year audit obligations.
- Descriptions and broad asset types cannot establish land ownership, restricted
  access, statutory clearance, tender, or document authenticity.
- The chunks are a deterministic evidence foundation only. No RAG index, model,
  external explanation call, or compliance inference from prose exists.

# 19. Recommended Day 6

**Delay + Cost-Overrun Predictive Intelligence**

Day 6 has not been implemented. Explicit approval is required before proceeding.
