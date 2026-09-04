# 1. Day 8 Goal

Day 8 adds guideline-grounded explanation intelligence only. The completed flow reads frozen Day 1–7 work evidence, builds a deterministic minimized evidence bundle, retrieves direct Day-5 clause anchors plus local semantic context, optionally requests a strict Grok explanation, validates its grounding, and falls back to a deterministic explanation whenever Grok is unavailable or invalid. No FastAPI, frontend, database, authentication, officer-write workflow, deployment, automatic corrective action, self-learning, or Day-9 implementation was added.

# 2. Governance

Grok is an optional explanation component, not a detector or decision-maker. It cannot calculate or alter review priority, detector results, predictions, duplicate status, or compliance results. It cannot infer intent or issue a final verdict. Review-priority values and contribution points are copied from the frozen Day-7 artifacts. Only an authorized human reviewer decides whether follow-up is warranted.

The normal Day-8 runner is offline-safe and makes no xAI request. A request can occur only when an API key exists and `--live-smoke` is explicitly supplied; the runner limits that smoke test to one through five cases.

# 3. Verified Guideline Source

The sole RAG corpus is `data/processed/guideline_chunks.json`, created from the locally verified *MPLADS Guidelines 2023 — Second Edition, 14 March 2023*. The manifest reports 70 physical PDF pages and 61 extractable page-aligned chunks. Runtime loading fails closed unless all chunk source hashes equal the manifest hash:

`2E4AF29D2FAAADBA4E8DADB16C30D56318AF23CD062436260ACA11777CEBC5E6`

No evaluation data, web search result, or unverified external document is added to the corpus.

# 4. Local Embedding Index

All 61 chunks were embedded locally with `sentence-transformers/all-MiniLM-L6-v2`. The index has shape `61 × 384`, uses `float32` vectors with L2 unit normalization, and is stored in `data/processed/guideline_embeddings.npy`. The encoder is loaded from the project cache with `local_files_only=True`; no external embedding service is called.

`guideline_embedding_metadata.json` records the ordered chunk IDs, model, 384-dimensional shape, guideline hash, normalization, sentence-transformers version 5.7.0, creation timestamp, and chunk-text contract hash `E7FBD3EBFBFCDBD0C420E802EF6F80C8CFAA0E6584458F98398E52BD5E5A3FBF`. The index is reused when the model, ordered IDs, chunk text, and guideline hash are unchanged.

# 5. Retrieval Design

Retrieval has two channels:

1. retain every unique direct chunk linked by actionable Day-5 compliance evidence;
2. append up to five highest-cosine local semantic chunks not already retained.

Direct references are ordered first and cannot be displaced by semantic results. The configured semantic `top_k` is 5 and the ordinary total context cap is 10; if direct references alone ever exceed the cap, all direct references still survive. Cosine similarity is recorded only as a retrieval score, never as confidence that a violation occurred.

# 6. Direct-Clause Retrieval

The 3,000 work bundles contain 4,492 work-to-chunk direct references across 2,132 works and five unique chunks: `P019`, `P020`, `P021`, `P026`, and `P051`. The retrieval audit tested 10 direct references across five compliance cases. Every tested direct chunk remained in final context.

Direct retrieval is triggered only by actionable Day-5 `REVIEW` or `NON_COMPLIANT` evidence containing a verified chunk ID. It is marked `DIRECT_RULE_REFERENCE`. Semantic retrieval never creates a new compliance result.

# 7. Semantic Retrieval

Queries are built from minimized fields: lifecycle, sector/sub-sector, Day-7 evidence codes, alert types, and deterministic rule title/clause metadata. Query embedding and cosine comparison are entirely local.

Representative audited results include:

| Category | Work | Direct chunks retained | Semantic top results |
|---|---|---|---|
| Compliance | W-001937 | P021, P051 | P037, P062, P042, P030, P015 |
| Duplicate | W-001966 | P021, P051 | P037, P062, P042, P015, P030 |
| Payment/execution | W-000090 | P021, P051 | P037, P062, P015, P042, P030 |
| Cost-overrun warning | W-002240 | P019 | P015, P025, P062, P053, P067 |
| Trend context | W-000934 | P019, P051 | P062, P015, P042, P067, P016 |

The non-compliance analytical categories above may retrieve context, but the explanation explicitly states that semantic similarity does not establish clause applicability or a compliance conclusion.

# 8. Evidence Bundle

`build_explanation_evidence(work_id)` reads existing artifacts only. Each bundle retains:

- the exact Day-7 priority score, band, ranks, evidence coverage, and positive family contributions;
- Day-7 alerts and evidence codes;
- lifecycle anomaly percentile and strongest robust peer evidence;
- only conservative Day-4.1 `review_candidate=true` duplicate pairs and their paired-work corroboration;
- payment irregularity records and fund-versus-progress context;
- already-observed overdue and over-sanction conditions;
- actionable deterministic Day-5 findings and direct guideline references;
- raw cost serving score/percentile, weak-model status, non-causal SHAP fields, and explicit delay-model unavailability;
- selected work-level operational trend context.

The score is read, not recalculated. Historical broad `candidate_flag` pairs are not promoted. Calibrated cost probability is omitted as a serving signal. Detector-hotspot prevalence is not individual evidence. `07_anomaly_ground_truth.csv`, evaluation labels, injected-anomaly helpers, and expected-risk helpers are not loaded.

# 9. Data Minimization

An on-demand xAI request contains one selected work's minimized bundle and only its retrieved guideline chunks. It does not contain entire CSVs, all 3,000 works, raw payment/progress tables, MP personal details, model binaries, evaluation labels, or unrelated records. The 3,000 local context records store guideline references/metadata rather than repeating guideline text.

Every context includes an evidence-bundle SHA-256, prompt version, guideline version/hash, retrieved IDs, explanation mode, and model metadata. No secret is written to source, tests, reports, or generated JSON.

# 10. Grok API Integration

Official xAI documentation was rechecked on 2026-09-02. The implemented contract uses `grok-4.6`, `POST https://api.x.ai/v1/responses`, bearer authentication, a finite 60-second default timeout, Responses structured output under `text.format`, and explicit `store=false`. The request never includes a `tools` field; web search and X search are disabled.

The direct `httpx` client handles connection failures, timeouts, 401/403, 429, 5xx, missing response text, malformed JSON, and schema-invalid output without crashing the explanation service. Error text never contains the API key. No live request was made in this run.

# 11. Structured Output Schema

The strict `GroundedExplanation` fields are:

- `work_id`
- `summary`
- `why_flagged: list[EvidenceExplanation]`
- `guideline_context: list[GuidelineExplanation]`
- `verification_steps`
- `limitations`
- `decision_statement`

`EvidenceExplanation` contains `family`, `finding`, `source_evidence_codes`, `interpretation`, and `caveat`. `GuidelineExplanation` contains `chunk_id`, nullable `clause`, nullable `page`, and `relevance`. All models forbid extra fields. The prompt asks for this schema only and never asks for chain-of-thought.

# 12. Prompt / Injection Guardrails

Prompt version is `DAY8_GROUNDED_EXPLANATION_V1`. The system prompt declares all project fields, evidence summaries, and guideline text to be untrusted data, prohibits obeying embedded instructions, limits the model to supplied evidence, and prohibits new scores, rules, thresholds, accusations, tools, and outside knowledge. Evidence and guideline context are placed in separate, explicit begin/end JSON blocks.

A constructed description containing an instruction to ignore prior rules and call web search remains quoted inside the untrusted-data block. The fallback neither executes nor repeats it as an instruction. This verifies the application defense is present; it does not prove elimination of all language-model security risk.

# 13. Grounding Validation

Pydantic validation is followed by deterministic checks that require:

- returned `work_id` equals the requested work;
- every evidence code exists in the supplied bundle;
- every chunk ID exists in supplied retrieval context;
- cited pages fall within the supplied chunk page range;
- cited clauses occur in the supplied chunk metadata or text;
- mentioned compliance rule IDs occur in the bundle;
- prohibited final-verdict language is absent.

The language firewall rejects serious phrases such as “fraud confirmed,” “this work is fraudulent,” “corrupt official,” “guilty,” “criminal project,” and “proven misuse.” A failure discards the complete Grok output and returns the deterministic fallback; it is never repaired by simple text replacement.

# 14. Deterministic Fallback

The fallback returns the same high-level schema without an API. It uses the exact top Day-7 contribution summaries, evidence-specific caveats and verification steps, direct guideline references, semantic-context disclaimers, and persistent limitations.

Representative output for W-001937 begins: “Work W-001937 has CRITICAL review priority at 89.442/100 (overall rank 1).” It then states the exact compliance, payment/execution, and duplicate-review contribution evidence. Its decision statement says: “This review-support evidence does not establish fraud or wrongdoing; an authorized officer must verify source records before deciding what follow-up, if any, is warranted.”

# 15. Representative Explanation Cases

The retrieval audit covers five compliance cases plus distinct duplicate, payment/execution, cost-overrun, and trend-context cases. The 3,000 local fallback explanations cover every unique Day-7 priority record. Each case preserves exact evidence identifiers and separates deterministic findings from statistical, predictive, or aggregate context.

For duplicate review the fallback requests comparison of sanction orders, locations, scope, and physical implementation. For payments it requests reconciliation of request, authorization, release, invoice, and PFMS/source records. Compliance asks for the exact cited rule document/field. Observed conditions ask whether approved extensions or cost variations apply. Predictive and trend evidence carry explicit weakness and aggregate-context caveats.

# 16. Optional Live Smoke Result

Status: `SKIPPED_NO_XAI_API_KEY`.

The run did not include `--live-smoke`, no key was available, zero API calls were attempted, and Day 8 passed entirely through local and mocked tests. This is the expected offline-safe behavior. A future explicit smoke run is capped at three cases by default and five maximum; it is integration evidence, not accuracy evaluation.

# 17. Outputs

Generated Day-8 artifacts:

- `data/processed/guideline_embeddings.npy`
- `data/processed/guideline_embedding_metadata.json`
- `data/processed/rag_retrieval_audit.json`
- `data/processed/explanation_context.jsonl` — exactly 3,000 records
- `data/processed/evaluation/day8_grok_live_smoke.json`
- `data/processed/day8_rag_summary.json`

Implementation is under `code/rag/`: models, embeddings, retrieval, evidence, prompt, Grok client, grounding, fallback, service, and runner modules. Day-8 tests are under `code/tests/`. `.env.example`, `pyproject.toml`, and `README.md` were updated without adding a real secret.

# 18. Tests

The focused Day-8 suite passed 32 tests. The final full suite passed 157 tests on Windows with Python 3.12.10 and pytest 8.4.2.

Coverage includes 61-chunk/index contracts, ordered metadata, normalized embeddings, deterministic bounded retrieval, direct-reference retention, bundle provenance, duplicate selectivity, predictive restrictions, prompt injection boundaries, mocked request/body/auth behavior, timeout and HTTP failures, malformed/schema-invalid responses, work/chunk/evidence/rule grounding failures, language firewall, offline fallback, 3,000-record output, and frozen-artifact hashes. No real API key is required.

# 19. Source / Prior-Artifact Integrity

The runner hashed 76 pre-existing processed/model artifacts before and after Day-8 generation and found no change. Tests separately pin the Day-7 trend/fusion outputs and Day-5 guideline artifacts byte-for-byte, while existing regression tests pin earlier governed outputs/models.

All 12 CSV hashes in `Demo-data` remained unchanged. Source CSVs were not modified, moved, renamed, overwritten, or used as an output location. Ground truth remained evaluation-only and outside the production evidence repository. Payments and progress remained separate; no earlier feature, detector, compliance, prediction, trend, or fusion artifact was regenerated.

# 20. Limitations

- Grok does not detect fraud and does not decide compliance.
- Retrieval similarity is not proof of guideline applicability.
- Only deterministic Day-5 rules establish compliance results.
- Generated explanations are grounded summaries of existing evidence.
- Prompt-injection defenses reduce risk but cannot prove its elimination.
- External API availability and provider behavior are not guaranteed.
- The deterministic fallback preserves application functionality without xAI.
- Source data remains synthetic.
- Day-7 review-priority policy remains prototype engineering policy.
- The weak cost-overrun model remains secondary evidence.
- The delay predictive model remains unavailable because of insufficient class balance.
- The 61 page-aligned chunks favor traceability over fine-grained semantic segmentation.

# 21. Recommended Day 9

The recommended next step is **Day 9 — FastAPI Backend + Next.js Frontend + Integration**. Day 9 was not started or implemented.

# Day 8.1 — Groq Provider Integration

The external explanation provider was changed from xAI Grok to GroqCloud because
the project selected Groq's free-tier API for on-demand hackathon explanations.
This is a provider-only correction: the 61-chunk local MiniLM index, direct clause
anchors, semantic retrieval, evidence bundles, Pydantic schema, prompt-injection
boundaries, grounding checks, language firewall, and deterministic fallback were
not redesigned.

Official Groq documentation was verified on 2026-09-02. The configured model is
`openai/gpt-oss-120b`, which is currently listed by Groq and supports strict JSON
Schema output. The client uses:

- provider: `groq`
- base URL: `https://api.groq.com/openai/v1`
- endpoint: `POST /chat/completions`
- response format: strict `json_schema`
- tool policy: `tool_choice=none`, with no tools, browser search, web search, code
  execution, external retrieval, or Groq Compound

The active request contains no xAI-specific `store` field. Privacy continues to
come from case-level data minimization: only one selected work's structured
evidence and retrieved local guideline chunks are eligible for transmission.

The internal Day-9-facing method is provider-neutral:
`explain_work(work_id, use_llm=True)`. Explanation metadata records provider
`groq`, configured model `openai/gpt-oss-120b`, prompt version, guideline hash,
evidence-bundle hash, retrieved IDs, and either `GROQ_GROUNDED` or
`DETERMINISTIC_FALLBACK`. Provider failure never changes risk or compliance.

Account-specific model access is preflighted through `/models` only for an
explicit live smoke run. If the approved model is unavailable, execution stops;
the client never substitutes another model. Rate limits fall back immediately
and preserve any `Retry-After` value as safe diagnostic metadata without an
uncontrolled retry loop.

No `GROQ_API_KEY` was present and `--live-smoke` was not requested. Status is
`SKIPPED_NO_GROQ_API_KEY`, with zero external calls. Normal operation and pytest
require no real key. The focused provider/grounding/output suite passed 43 tests,
and the final complete Day 1–8.1 regression suite passed 168 tests in 63.29 seconds
on Python 3.12.10.

The Day-8 embedding file, embedding metadata, and retrieval audit remained
byte-identical after the migration. The historical Day-8 sections above are
retained as implementation history; this Day-8.1 section defines the current
serving provider. Day 1–7 intelligence and all 12 read-only Demo-data CSVs remain
unchanged. Day 9 was not started.

# Day 8.2 — Groq Payload and Grounding Hardening

## Scope and Day-8.1 failure analysis

Day 8.2 changed only the external explanation-serving path. The Day-5 compliance
engine, Day-7 review-priority policy, local 61-chunk RAG index, retrieval audit,
detector outputs, embedding model, deterministic fallback, and grounding policy
were not redesigned.

The Day-8.1 failures had two distinct causes:

- `W-001937` and `W-001966` were rejected by Groq with HTTP 413. Their serialized
  requests were 37,209 and 36,372 bytes respectively.
- `W-002240` received a schema-valid response, but deterministic grounding rejected
  it for `UNSUPPORTED_CLAUSE:MPLADS-2023-P019:3.2.4; 3.2.6` and
  `INVENTED_COMPLIANCE_RULE:['MPLADS-3.2.4']`. The model placed two supplied clause
  identifiers into one citation field and shortened the actual allowed rule ID
  `MPLADS-3.2.4-SANCTION-45D`. There was no work-ID, chunk-ID, page, verdict-language,
  or schema failure in that case.

## Original and minimized request measurements

The original measurements were captured locally before implementation changes.
`evidence items` in the legacy request uses the old allowed-evidence list as a
consistent proxy because Day 8.1 sent the whole nested bundle rather than an
explicit selected-item list.

| Work | Version | Request bytes | System chars | Evidence chars | Guideline chars | Schema chars | Evidence items | Direct chunks | Semantic chunks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| W-001937 | Day 8.1 | 37,209 | 1,271 | 13,940 | 18,049 | 1,665 | 19 | 2 | 5 |
| W-001937 | Day 8.2 | 14,894 | 820 | 5,567 | 4,478 | 1,754 | 7 | 2 | 2 |
| W-001966 | Day 8.1 | 36,372 | 1,271 | 13,154 | 18,052 | 1,665 | 18 | 2 | 5 |
| W-001966 | Day 8.2 | 14,558 | 820 | 5,305 | 4,478 | 1,727 | 6 | 2 | 2 |
| W-002240 | Day 8.1 | 32,000 | 1,271 | 13,042 | 13,909 | 1,665 | 20 | 1 | 5 |
| W-002240 | Day 8.2 | 13,484 | 820 | 5,200 | 3,678 | 1,708 | 8 | 1 | 2 |

The request-local enums make the serialized schema slightly larger while keeping
the same user-facing `GroundedExplanation` structure. Total request size fell by
about 58–60 percent and stayed below the conservative 18,000-byte internal budget.

## External evidence-selection policy

Local retrieval remains unchanged: it retains every direct rule reference and up
to five semantic chunks. A new deterministic `EXTERNAL_LLM_CONTEXT_SELECTION`
step prepares the provider request separately.

The external evidence cap is eight summarized items per work. Positive Day-7
contributing families are retained in ranked order and enriched, where applicable,
with compact deterministic compliance, duplicate-review, observed-condition,
payment/fund-progress, weak-prediction, or trend facts. Deterministic actionable
compliance evidence, duplicate review candidates, observed overdue/over-sanction
conditions, and all top-contribution items are mandatory when present. Additional
alerts and lower-priority context fill only remaining capacity. No LLM selects the
items and no raw source table row is transmitted.

The external guideline policy retains every unique direct rule chunk and sends at
most two semantic chunks. Direct references are converted into one exact
clause-centered excerpt per referenced clause; semantic context uses a compact,
deterministically selected relevant paragraph excerpt. The smoke cases retained
2/2/1 unique direct chunks, represented by 3/3/2 direct excerpts, plus two semantic
excerpts each.

Every excerpt records its source chunk ID, source-chunk SHA-256, excerpt SHA-256,
page, chapter, exact clause where applicable, guideline version/hash, and start/end
character offsets. Tests prove every excerpt is an exact substring of the verified
local chunk. Guideline text is never paraphrased before transmission.

If the 18,000-byte request budget is exceeded, semantic excerpts are removed first,
then optional lower-priority analytical items. Mandatory direct context is never
removed. If mandatory evidence exceeds the eight-item cap or mandatory direct
context alone exceeds the byte budget, Groq is skipped and deterministic fallback
is returned without an external call.

## Identifier and grounding hardening

Each request now explicitly supplies `ALLOWED_EVIDENCE_CODES`,
`ALLOWED_GUIDELINE_CHUNK_IDS`, `ALLOWED_COMPLIANCE_RULE_IDS`, and exact allowed
clause IDs. Request-local JSON Schema constraints bind `work_id`, evidence-code,
chunk-ID, and clause fields to those values. The prompt directs the model to copy
identifiers exactly and forbids shortening or combining them. Semantic context
cannot establish a compliance result; the required no-conclusion sentence remains
explicit.

Grounding was not weakened. Existing work, evidence, chunk, page, clause, rule,
and verdict checks remain in force. External responses receive the tighter selected
evidence/rule allow-list and a per-chunk clause allow-list. A fabricated identifier
still discards the entire response and activates fallback.

## Day-8.2 live smoke result

The authorized smoke reran exactly the three representative cases once. There were
no retries after provider rate limiting.

| Work / case | Request bytes | Evidence items | Guideline excerpts | HTTP | Schema | Grounding | Final mode |
|---|---:|---:|---:|---|---|---|---|
| W-001937 — multi-signal completion | 14,894 | 7 | 5 | 200 | PASSED | PASSED | GROQ_GROUNDED |
| W-001966 — duplicate review | 14,558 | 6 | 5 | 429 (`Retry-After: 12`) | NOT_RUN | NOT_RUN | DETERMINISTIC_FALLBACK |
| W-002240 — execution early warning | 13,484 | 8 | 4 | 429 (`Retry-After: 8`) | NOT_RUN | NOT_RUN | DETERMINISTIC_FALLBACK |

The HTTP 413 condition was eliminated for all submitted requests. The one request
accepted for inference passed both schema and deterministic grounding validation.
The other two were safely rate-limited before a model response, and the controlled
no-retry policy used deterministic fallback. Therefore the desired 3/3 criterion
was not achieved in this single bounded run; the exact remaining cause was provider
HTTP 429, not payload size or weakened validation.

Safe request measurements and outcomes are stored in
`data/processed/evaluation/day8_2_payload_diagnostics.json`. Neither that artifact
nor the smoke artifact contains an API key, an Authorization value, or a credential
field.

## Tests and integrity

The focused hardening suite passed 37 tests. The complete Day-1 through Day-8.2
suite passed **176 tests in 70.99 seconds** under the project Python 3.12 virtual
environment before the live smoke run.

Tests cover payload reduction, deterministic selection, the eight-item cap, direct
reference retention, semantic-first reduction, exact-substring excerpt traceability,
verified text provenance, local budget fallback before any HTTP call, secret-free
diagnostics, transmitted identifier allow-lists, unchanged grounding rejection,
fabricated identifiers, helper/ground-truth exclusion, frozen local RAG hashes,
prior governed artifact hashes, and all 12 Demo-data hashes.

Post-smoke verification confirmed the local embeddings, embedding metadata,
retrieval audit, 3,000-record explanation context, and Day-8 summary remained
byte-identical. The full regression suite confirmed the governed Day-1 through
Day-7 artifacts remained unchanged. All 12 `Demo-data` CSV hashes remain unchanged,
ground truth remains evaluation-only, and deterministic fallback remains fully
operational. Day 9 was not started.
