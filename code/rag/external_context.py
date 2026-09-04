"""Deterministic provider-only evidence selection and guideline excerpting."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .groq_client import GroqClient, GroqSettings, serialized_request_size
from .models import ExternalGuidelineExcerpt, RetrievedGuidelineChunk
from .prompt import SYSTEM_PROMPT, build_external_user_prompt
from .retrieval import DIRECT_RULE_REFERENCE, SEMANTIC_SIMILARITY


EXTERNAL_EVIDENCE_CAP = 8
EXTERNAL_SEMANTIC_CHUNK_CAP = 2
EXTERNAL_REQUEST_BUDGET_BYTES = 18_000
DIRECT_EXCERPT_CHARACTER_LIMIT = 1_200
SEMANTIC_EXCERPT_CHARACTER_LIMIT = 650

# Captured locally before Day-8.2 changes. Counts use the old bundle's
# allowed-evidence list as the consistent evidence-item proxy.
DAY81_SMOKE_BASELINE: dict[str, dict[str, int]] = {
    "W-001937": {
        "request_json_bytes": 37_209,
        "system_prompt_characters": 1_271,
        "evidence_json_characters": 13_940,
        "guideline_context_characters": 18_049,
        "structured_output_schema_characters": 1_665,
        "evidence_item_count": 19,
        "direct_chunk_count": 2,
        "semantic_chunk_count": 5,
    },
    "W-001966": {
        "request_json_bytes": 36_372,
        "system_prompt_characters": 1_271,
        "evidence_json_characters": 13_154,
        "guideline_context_characters": 18_052,
        "structured_output_schema_characters": 1_665,
        "evidence_item_count": 18,
        "direct_chunk_count": 2,
        "semantic_chunk_count": 5,
    },
    "W-002240": {
        "request_json_bytes": 32_000,
        "system_prompt_characters": 1_271,
        "evidence_json_characters": 13_042,
        "guideline_context_characters": 13_909,
        "structured_output_schema_characters": 1_665,
        "evidence_item_count": 20,
        "direct_chunk_count": 1,
        "semantic_chunk_count": 5,
    },
}

_CLAUSE_PATTERN = re.compile(r"\d+(?:\.\d+)+")
_WORD_PATTERN = re.compile(r"[a-z0-9]{4,}")


@dataclass(frozen=True)
class _EvidenceCandidate:
    payload: dict[str, Any]
    priority: int
    mandatory: bool


@dataclass(frozen=True)
class ExternalRequestPackage:
    user_prompt: str
    request_payload: dict[str, Any]
    evidence_items: list[dict[str, Any]]
    guideline_excerpts: list[ExternalGuidelineExcerpt]
    allowed_evidence_codes: list[str]
    allowed_guideline_chunk_ids: list[str]
    allowed_compliance_rule_ids: list[str]
    allowed_clause_ids: list[str]
    allowed_clauses_by_chunk: dict[str, set[str]]
    within_budget: bool
    failure_reason: str | None
    diagnostics: dict[str, Any]

    def validation_bundle(self, work_id: str) -> dict[str, Any]:
        return {
            "work_id": work_id,
            "allowed_evidence_codes": self.allowed_evidence_codes,
            "compliance": {
                "actionable_findings": [
                    {"rule_id": rule_id}
                    for rule_id in self.allowed_compliance_rule_ids
                ]
            },
        }


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _drop_empty(item)) not in (None, [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if (cleaned := _drop_empty(item)) not in (None, [], {})
        ]
    return value


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _clauses(value: Any) -> list[str]:
    return _unique(_CLAUSE_PATTERN.findall(str(value or "")))


def _compliance_details(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _drop_empty(
            {
                "rule_id": str(row["rule_id"]),
                "result": row.get("result"),
                "severity": row.get("severity"),
                "evidence_summary": row.get("evidence"),
                "direct_guideline_chunk_ids": row.get("guideline_chunk_ids", []),
                "allowed_clause_ids": _clauses(row.get("guideline_clause")),
                "page": row.get("guideline_page"),
            }
        )
        for row in bundle["compliance"]["actionable_findings"]
    ]


def _enrich_top_contribution(
    row: dict[str, Any], bundle: dict[str, Any]
) -> dict[str, Any]:
    family = str(row["family"])
    item: dict[str, Any] = {
        "family": family,
        "evidence_type": "DAY7_TOP_CONTRIBUTION",
        "summary": str(row["evidence_summary"]),
        "source_evidence_codes": [str(row["evidence_code"])],
        "contribution_points": row.get("contribution_points"),
    }
    if family == "COMPLIANCE":
        findings = _compliance_details(bundle)
        item["deterministic_compliance_findings"] = findings
        item["source_evidence_codes"] = _unique(
            item["source_evidence_codes"]
            + [str(entry["rule_id"]) for entry in findings]
        )
    elif family == "DUPLICATE_REVIEW":
        candidates = bundle["duplicate"]["review_candidates_only"]
        if candidates:
            best = candidates[0]
            item["duplicate_review_candidate"] = _drop_empty(
                {
                    "pair_id": best.get("pair_id"),
                    "paired_work_id": best.get("paired_work_id"),
                    "similarity_score_0_100": best.get(
                        "duplicate_similarity_score_0_100"
                    ),
                    "geographic_distance_km": best.get("geographic_distance_km"),
                    "same_village": best.get("same_village"),
                    "sector_match": best.get("sector_match"),
                    "review_policy_reason": best.get("review_policy_reason"),
                }
            )
            item["source_evidence_codes"] = _unique(
                item["source_evidence_codes"] + [str(best["evidence_code"])]
            )
    elif family == "OBSERVED_CONDITIONS":
        observed = bundle["observed_conditions"]
        item["observed_facts"] = observed
        if observed.get("already_overdue_as_of"):
            item["source_evidence_codes"].append("ALREADY_OVERDUE_AS_OF")
        if observed.get("already_over_sanction_as_of"):
            item["source_evidence_codes"].append("ALREADY_OVER_SANCTION_AS_OF")
        item["source_evidence_codes"] = _unique(item["source_evidence_codes"])
    elif family == "PAYMENT_EXECUTION":
        payment = bundle["payment_execution"]
        selected = sorted(
            payment["selected_evidence"],
            key=lambda value: (
                str(value.get("signal_severity", "")),
                str(value.get("signal_code", "")),
            ),
            reverse=True,
        )[:2]
        item["payment_execution_summary"] = _drop_empty(
            {
                **payment["summary"],
                "selected_signal_summaries": [
                    {
                        "signal_code": value.get("signal_code"),
                        "severity": value.get("signal_severity"),
                        "summary": value.get("evidence"),
                    }
                    for value in selected
                ],
                "fund_progress": payment["fund_progress_context"],
            }
        )
        item["source_evidence_codes"] = _unique(
            item["source_evidence_codes"]
            + [str(value["signal_code"]) for value in selected]
        )
    elif family == "COST_OVERRUN_PREDICTION":
        prediction = bundle["prediction"]
        item["weak_prediction_context"] = _drop_empty(
            {
                "serving_score": prediction.get("cost_overrun_serving_score"),
                "serving_percentile_0_100": prediction.get(
                    "cost_overrun_serving_percentile_0_100"
                ),
                "model_quality_status": prediction.get(
                    "cost_overrun_model_quality_status"
                ),
                "calibrated_probability_used": False,
            }
        )
    elif family == "OPERATIONAL_TREND_CONTEXT":
        item["trend_context"] = bundle["trend"]
    return _drop_empty(item)


def _special_candidate(
    family: str, bundle: dict[str, Any], *, priority: int, mandatory: bool
) -> _EvidenceCandidate | None:
    if family == "COMPLIANCE" and bundle["compliance"]["actionable_findings"]:
        findings = _compliance_details(bundle)
        payload = {
            "family": family,
            "evidence_type": "DETERMINISTIC_DAY5_COMPLIANCE",
            "summary": "Supplied deterministic Day-5 actionable findings.",
            "source_evidence_codes": [str(row["rule_id"]) for row in findings],
            "deterministic_compliance_findings": findings,
        }
    elif family == "DUPLICATE_REVIEW" and bundle["duplicate"]["review_candidates_only"]:
        best = bundle["duplicate"]["review_candidates_only"][0]
        payload = {
            "family": family,
            "evidence_type": "CORROBORATED_DUPLICATE_REVIEW_CANDIDATE",
            "summary": str(best.get("evidence_summary") or best.get("review_policy_reason")),
            "source_evidence_codes": [str(best["evidence_code"])],
            "duplicate_review_candidate": _drop_empty(
                {
                    "pair_id": best.get("pair_id"),
                    "paired_work_id": best.get("paired_work_id"),
                    "similarity_score_0_100": best.get(
                        "duplicate_similarity_score_0_100"
                    ),
                }
            ),
        }
    elif family == "OBSERVED_CONDITIONS" and any(
        bundle["observed_conditions"].get(key)
        for key in ("already_overdue_as_of", "already_over_sanction_as_of")
    ):
        observed = bundle["observed_conditions"]
        codes = []
        if observed.get("already_overdue_as_of"):
            codes.append("ALREADY_OVERDUE_AS_OF")
        if observed.get("already_over_sanction_as_of"):
            codes.append("ALREADY_OVER_SANCTION_AS_OF")
        payload = {
            "family": family,
            "evidence_type": "OBSERVED_DETERMINISTIC_CONDITION",
            "summary": "Observed timing/cost conditions from the controlled snapshot.",
            "source_evidence_codes": codes,
            "observed_facts": observed,
        }
    elif family == "PAYMENT_EXECUTION" and (
        bundle["payment_execution"]["selected_evidence"]
        or bundle["payment_execution"]["fund_progress_context"]
    ):
        row = {
            "family": family,
            "evidence_summary": "Selected payment and fund-progress review context.",
            "evidence_code": "PAYMENT_EXECUTION_CONTEXT",
            "contribution_points": None,
        }
        payload = _enrich_top_contribution(row, bundle)
        payload["evidence_type"] = "PAYMENT_AND_FUND_PROGRESS_CONTEXT"
    elif family == "COST_OVERRUN_PREDICTION" and bundle["prediction"].get(
        "cost_overrun_serving_score"
    ) is not None:
        row = {
            "family": family,
            "evidence_summary": "Weak secondary raw-XGBoost early-warning context.",
            "evidence_code": "COST_OVERRUN_SERVING_PERCENTILE",
            "contribution_points": None,
        }
        payload = _enrich_top_contribution(row, bundle)
        payload["evidence_type"] = "WEAK_PREDICTIVE_CONTEXT"
    elif family == "OPERATIONAL_TREND_CONTEXT" and bundle["trend"].get(
        "operational_trend_deviation_flag"
    ):
        row = {
            "family": family,
            "evidence_summary": "Supported operational trend context.",
            "evidence_code": "OPERATIONAL_TREND_CONTEXT",
            "contribution_points": None,
        }
        payload = _enrich_top_contribution(row, bundle)
        payload["evidence_type"] = "AGGREGATE_TREND_CONTEXT"
    else:
        return None
    return _EvidenceCandidate(_drop_empty(payload), priority, mandatory)


def select_external_evidence(
    bundle: dict[str, Any], *, cap: int = EXTERNAL_EVIDENCE_CAP
) -> tuple[list[_EvidenceCandidate], bool]:
    """Select compact items deterministically without consulting an LLM."""

    if cap < 1:
        raise ValueError("External evidence cap must be positive")
    family_priority = {
        "OBSERVED_CONDITIONS": 10,
        "PAYMENT_EXECUTION": 20,
        "COMPLIANCE": 30,
        "DUPLICATE_REVIEW": 40,
        "PEER_BENCHMARK": 50,
        "ANOMALY": 60,
        "COST_OVERRUN_PREDICTION": 70,
        "OPERATIONAL_TREND_CONTEXT": 80,
    }
    candidates = [
        _EvidenceCandidate(
            _enrich_top_contribution(row, bundle),
            priority=family_priority.get(str(row["family"]), 90) + index,
            mandatory=True,
        )
        for index, row in enumerate(bundle["top_contributions"])
    ]
    represented = {item.payload["family"] for item in candidates}
    for family, priority in (
        ("OBSERVED_CONDITIONS", 10),
        ("PAYMENT_EXECUTION", 20),
        ("COMPLIANCE", 30),
        ("DUPLICATE_REVIEW", 40),
    ):
        if family not in represented:
            item = _special_candidate(
                family, bundle, priority=priority, mandatory=True
            )
            if item:
                candidates.append(item)
                represented.add(family)

    selected_codes = {
        str(code)
        for item in candidates
        for code in item.payload.get("source_evidence_codes", [])
    }
    extra_alerts = [
        row
        for row in sorted(
            bundle["alerts"],
            key=lambda value: (
                -float(value.get("alert_strength_0_100") or 0),
                str(value.get("alert_type", "")),
            ),
        )
        if str(row["evidence_code"]) not in selected_codes
    ][:3]
    if extra_alerts:
        candidates.append(
            _EvidenceCandidate(
                _drop_empty(
                    {
                        "family": "STRONG_DETERMINISTIC_ALERTS",
                        "evidence_type": "DAY7_ALERT",
                        "summary": "Additional high-strength review alerts.",
                        "source_evidence_codes": [
                            str(row["evidence_code"]) for row in extra_alerts
                        ],
                        "alerts": [
                            {
                                "alert_type": row.get("alert_type"),
                                "strength_0_100": row.get("alert_strength_0_100"),
                                "summary": row.get("alert_summary"),
                            }
                            for row in extra_alerts
                        ],
                    }
                ),
                priority=45,
                mandatory=False,
            )
        )

    for family, priority in (
        ("COST_OVERRUN_PREDICTION", 70),
        ("OPERATIONAL_TREND_CONTEXT", 80),
    ):
        if family not in represented:
            item = _special_candidate(
                family, bundle, priority=priority, mandatory=False
            )
            if item:
                candidates.append(item)
                represented.add(family)

    mandatory = sorted(
        (item for item in candidates if item.mandatory),
        key=lambda item: item.priority,
    )
    if len(mandatory) > cap:
        return mandatory[:cap], True
    optional = sorted(
        (item for item in candidates if not item.mandatory),
        key=lambda item: item.priority,
    )
    return mandatory + optional[: cap - len(mandatory)], False


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    start = max(0, start)
    end = min(len(text), end)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _clause_span(text: str, clause: str) -> tuple[int, int]:
    headers = list(
        re.finditer(r"(?m)^[ \t]*(\d+(?:\.\d+)+)\s+", text)
    )
    for index, match in enumerate(headers):
        if match.group(1) != clause:
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        if end - match.start() > DIRECT_EXCERPT_CHARACTER_LIMIT:
            end = match.start() + DIRECT_EXCERPT_CHARACTER_LIMIT
        return _trimmed_span(text, match.start(), end)
    occurrence = text.find(clause)
    if occurrence >= 0:
        return _trimmed_span(
            text,
            occurrence - 150,
            occurrence + DIRECT_EXCERPT_CHARACTER_LIMIT - 150,
        )
    return _trimmed_span(text, 0, DIRECT_EXCERPT_CHARACTER_LIMIT)


def _semantic_span(text: str, query: str) -> tuple[int, int]:
    terms = set(_WORD_PATTERN.findall(query.casefold()))
    paragraphs = [
        (match.start(1), match.end(1), match.group(1))
        for match in re.finditer(
            r"(?:^|\n\s*\n)(.*?)(?=\n\s*\n|\Z)", text, flags=re.DOTALL
        )
        if match.group(1).strip()
    ]
    if not paragraphs:
        return _trimmed_span(text, 0, SEMANTIC_EXCERPT_CHARACTER_LIMIT)
    start, end, paragraph = max(
        paragraphs,
        key=lambda value: (
            sum(term in value[2].casefold() for term in terms),
            -value[0],
        ),
    )
    if end - start <= SEMANTIC_EXCERPT_CHARACTER_LIMIT:
        return _trimmed_span(text, start, end)
    lowered = paragraph.casefold()
    hits = [lowered.find(term) for term in sorted(terms) if term in lowered]
    focus = min(hits) if hits else 0
    relative_start = max(0, focus - 150)
    relative_start = min(
        relative_start, len(paragraph) - SEMANTIC_EXCERPT_CHARACTER_LIMIT
    )
    return _trimmed_span(
        text,
        start + relative_start,
        start + relative_start + SEMANTIC_EXCERPT_CHARACTER_LIMIT,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _excerpt(
    chunk: RetrievedGuidelineChunk,
    start: int,
    end: int,
    *,
    clause: str | None,
) -> ExternalGuidelineExcerpt:
    text = chunk.text[start:end]
    return ExternalGuidelineExcerpt(
        chunk_id=chunk.chunk_id,
        page=chunk.page_start,
        chapter=chunk.chapter,
        clause=clause,
        retrieval_method=chunk.retrieval_method,
        guideline_version=chunk.guideline_version,
        guideline_sha256=chunk.guideline_sha256,
        source_chunk_id=chunk.chunk_id,
        source_chunk_sha256=_sha256_text(chunk.text),
        excerpt_sha256=_sha256_text(text),
        start_character_offset=start,
        end_character_offset=end,
        excerpt_text=text,
    )


def _direct_clause_map(bundle: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for finding in bundle["compliance"]["actionable_findings"]:
        clauses = _clauses(finding.get("guideline_clause"))
        for chunk_id in finding.get("guideline_chunk_ids", []):
            result.setdefault(str(chunk_id), [])
            result[str(chunk_id)] = _unique(result[str(chunk_id)] + clauses)
    return result


def build_external_guideline_excerpts(
    bundle: dict[str, Any],
    retrieved: list[RetrievedGuidelineChunk],
    query: str,
    *,
    semantic_cap: int = EXTERNAL_SEMANTIC_CHUNK_CAP,
) -> list[ExternalGuidelineExcerpt]:
    """Keep all direct references and compact at most two semantic chunks."""

    direct_clauses = _direct_clause_map(bundle)
    excerpts: list[ExternalGuidelineExcerpt] = []
    semantic_count = 0
    for chunk in retrieved:
        if chunk.retrieval_method == DIRECT_RULE_REFERENCE:
            clauses = direct_clauses.get(chunk.chunk_id, [])
            if clauses:
                for clause in clauses:
                    start, end = _clause_span(chunk.text, clause)
                    excerpts.append(
                        _excerpt(chunk, start, end, clause=clause)
                    )
            else:
                start, end = _trimmed_span(
                    chunk.text, 0, DIRECT_EXCERPT_CHARACTER_LIMIT
                )
                excerpts.append(_excerpt(chunk, start, end, clause=None))
        elif (
            chunk.retrieval_method == SEMANTIC_SIMILARITY
            and semantic_count < semantic_cap
        ):
            start, end = _semantic_span(chunk.text, query)
            excerpts.append(_excerpt(chunk, start, end, clause=None))
            semantic_count += 1
    return excerpts


def _identifiers(
    evidence_items: list[dict[str, Any]],
    excerpts: list[ExternalGuidelineExcerpt],
) -> tuple[list[str], list[str], list[str], list[str], dict[str, set[str]]]:
    codes = _unique(
        [
            str(code)
            for item in evidence_items
            for code in item.get("source_evidence_codes", [])
        ]
    )
    rules = _unique(
        [
            str(row["rule_id"])
            for item in evidence_items
            for row in item.get("deterministic_compliance_findings", [])
        ]
    )
    chunks = _unique([item.chunk_id for item in excerpts])
    clauses = _unique([item.clause for item in excerpts if item.clause])
    by_chunk: dict[str, set[str]] = {chunk_id: set() for chunk_id in chunks}
    for item in excerpts:
        if item.clause:
            by_chunk[item.chunk_id].add(item.clause)
    return codes, chunks, rules, clauses, by_chunk


def _build(
    bundle: dict[str, Any],
    candidates: list[_EvidenceCandidate],
    excerpts: list[ExternalGuidelineExcerpt],
    model: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    items = [candidate.payload for candidate in candidates]
    codes, chunks, rules, clauses, _ = _identifiers(items, excerpts)
    external_evidence = {
        "work_id": bundle["work_id"],
        "lifecycle_stage": bundle["lifecycle_stage"],
        "review_priority": bundle["review_priority"],
        "evidence_items": items,
    }
    excerpt_json = [item.model_dump(mode="json") for item in excerpts]
    user_prompt = build_external_user_prompt(
        external_evidence,
        excerpt_json,
        allowed_evidence_codes=codes,
        allowed_guideline_chunk_ids=chunks,
        allowed_compliance_rule_ids=rules,
        allowed_clause_ids=clauses,
    )
    client = GroqClient(GroqSettings(groq_api_key=None, groq_model=model))
    payload = client.request_payload(
        SYSTEM_PROMPT,
        user_prompt,
        allowed_work_id=str(bundle["work_id"]),
        allowed_evidence_codes=codes,
        allowed_chunk_ids=chunks,
        allowed_clause_ids=clauses,
    )
    components = {
        "system_prompt_characters": len(SYSTEM_PROMPT),
        "evidence_json_characters": len(
            json.dumps(
                external_evidence,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        "guideline_context_characters": len(
            json.dumps(
                excerpt_json,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        "structured_output_schema_characters": len(
            json.dumps(
                payload["response_format"]["json_schema"]["schema"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        ),
        "request_json_bytes": serialized_request_size(payload),
    }
    return user_prompt, payload, components


def prepare_external_request(
    bundle: dict[str, Any],
    retrieved: list[RetrievedGuidelineChunk],
    query: str,
    model: str,
    *,
    evidence_cap: int = EXTERNAL_EVIDENCE_CAP,
    semantic_cap: int = EXTERNAL_SEMANTIC_CHUNK_CAP,
    request_budget_bytes: int = EXTERNAL_REQUEST_BUDGET_BYTES,
) -> ExternalRequestPackage:
    """Prepare a deterministic bounded request or a local-fallback decision."""

    candidates, evidence_overflow = select_external_evidence(
        bundle, cap=evidence_cap
    )
    excerpts = build_external_guideline_excerpts(
        bundle, retrieved, query, semantic_cap=semantic_cap
    )
    original_semantic_count = sum(
        item.retrieval_method == SEMANTIC_SIMILARITY for item in excerpts
    )
    dropped_evidence = 0
    user_prompt, payload, components = _build(
        bundle, candidates, excerpts, model
    )
    if not evidence_overflow:
        while components["request_json_bytes"] > request_budget_bytes:
            semantic_indices = [
                index
                for index, item in enumerate(excerpts)
                if item.retrieval_method == SEMANTIC_SIMILARITY
            ]
            if semantic_indices:
                excerpts.pop(semantic_indices[-1])
            else:
                optional_indices = [
                    index
                    for index, item in enumerate(candidates)
                    if not item.mandatory
                ]
                if not optional_indices:
                    break
                candidates.pop(optional_indices[-1])
                dropped_evidence += 1
            user_prompt, payload, components = _build(
                bundle, candidates, excerpts, model
            )

    evidence_items = [candidate.payload for candidate in candidates]
    codes, chunks, rules, clauses, by_chunk = _identifiers(
        evidence_items, excerpts
    )
    within_budget = (
        not evidence_overflow
        and components["request_json_bytes"] <= request_budget_bytes
    )
    failure_reason = None
    if evidence_overflow:
        failure_reason = "MANDATORY_EVIDENCE_EXCEEDS_ITEM_CAP"
    elif not within_budget:
        failure_reason = "MANDATORY_DIRECT_CONTEXT_EXCEEDS_REQUEST_BUDGET"
    direct_chunks = {
        item.chunk_id
        for item in excerpts
        if item.retrieval_method == DIRECT_RULE_REFERENCE
    }
    semantic_chunks = {
        item.chunk_id
        for item in excerpts
        if item.retrieval_method == SEMANTIC_SIMILARITY
    }
    diagnostics = {
        **components,
        "internal_request_budget_bytes": request_budget_bytes,
        "within_internal_budget": within_budget,
        "budget_failure_reason": failure_reason,
        "evidence_item_cap": evidence_cap,
        "evidence_item_count": len(evidence_items),
        "guideline_excerpt_count": len(excerpts),
        "direct_chunk_count": len(direct_chunks),
        "direct_excerpt_count": sum(
            item.retrieval_method == DIRECT_RULE_REFERENCE for item in excerpts
        ),
        "semantic_chunk_count": len(semantic_chunks),
        "semantic_excerpt_count": sum(
            item.retrieval_method == SEMANTIC_SIMILARITY for item in excerpts
        ),
        "dropped_semantic_chunk_count": (
            original_semantic_count - len(semantic_chunks)
        ),
        "dropped_lower_priority_evidence_count": dropped_evidence,
        "allowed_evidence_code_count": len(codes),
        "allowed_guideline_chunk_id_count": len(chunks),
        "allowed_compliance_rule_id_count": len(rules),
        "credential_fields_logged": False,
    }
    return ExternalRequestPackage(
        user_prompt=user_prompt,
        request_payload=payload,
        evidence_items=evidence_items,
        guideline_excerpts=excerpts,
        allowed_evidence_codes=codes,
        allowed_guideline_chunk_ids=chunks,
        allowed_compliance_rule_ids=rules,
        allowed_clause_ids=clauses,
        allowed_clauses_by_chunk=by_chunk,
        within_budget=within_budget,
        failure_reason=failure_reason,
        diagnostics=diagnostics,
    )
