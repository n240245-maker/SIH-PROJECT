"""Post-schema grounding and language-firewall validation."""

from __future__ import annotations

import json
import re
from typing import Any

from .models import GroundedExplanation, RetrievedGuidelineChunk


PROHIBITED_VERDICT_PATTERNS = (
    r"\bfraud (?:detected|confirmed)\b",
    r"\bthis work is fraudulent\b",
    r"\bcorrupt official\b",
    r"\bguilty\b",
    r"\bcriminal project\b",
    r"\bproven misuse\b",
)

_RULE_PATTERN = re.compile(r"\b(?:MPLADS|CANDIDATE)-[A-Z0-9.][A-Z0-9._-]*\b")


class GroundingValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        super().__init__("; ".join(issues))
        self.issues = issues


def language_firewall_violations(value: Any) -> list[str]:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return [
        pattern
        for pattern in PROHIBITED_VERDICT_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def validate_grounded_explanation(
    explanation: GroundedExplanation,
    bundle: dict[str, Any],
    retrieved: list[RetrievedGuidelineChunk],
    *,
    allowed_clauses_by_chunk: dict[str, set[str]] | None = None,
) -> None:
    issues: list[str] = []
    if explanation.work_id != bundle["work_id"]:
        issues.append("WORK_ID_MISMATCH")
    allowed_codes = set(bundle["allowed_evidence_codes"])
    used_codes = {
        code for item in explanation.why_flagged for code in item.source_evidence_codes
    }
    unknown_codes = sorted(used_codes - allowed_codes)
    if unknown_codes:
        issues.append(f"UNKNOWN_EVIDENCE_CODES:{unknown_codes}")

    chunks = {chunk.chunk_id: chunk for chunk in retrieved}
    for item in explanation.guideline_context:
        chunk = chunks.get(item.chunk_id)
        if chunk is None:
            issues.append(f"UNKNOWN_CHUNK_ID:{item.chunk_id}")
            continue
        if item.page is not None and not chunk.page_start <= item.page <= chunk.page_end:
            issues.append(f"UNSUPPORTED_PAGE:{item.chunk_id}:{item.page}")
        if item.clause:
            clause = item.clause.strip()
            if (
                allowed_clauses_by_chunk is not None
                and clause not in allowed_clauses_by_chunk.get(item.chunk_id, set())
            ):
                issues.append(f"UNSUPPORTED_CLAUSE:{item.chunk_id}:{clause}")
                continue
            supported = clause in (chunk.clause_identifiers or "") or bool(
                re.search(rf"(?m)^\s*\*?{re.escape(clause)}\s", chunk.text)
            )
            if not supported:
                issues.append(f"UNSUPPORTED_CLAUSE:{item.chunk_id}:{clause}")

    allowed_rules = {
        str(row["rule_id"])
        for row in bundle["compliance"]["actionable_findings"]
    }
    allowed_chunk_ids = set(chunks)
    text = explanation.model_dump_json()
    mentioned_rules = set(_RULE_PATTERN.findall(text)) - allowed_chunk_ids
    invented_rules = sorted(mentioned_rules - allowed_rules)
    if invented_rules:
        issues.append(f"INVENTED_COMPLIANCE_RULE:{invented_rules}")
    verdicts = language_firewall_violations(text)
    if verdicts:
        issues.append(f"PROHIBITED_VERDICT_LANGUAGE:{verdicts}")
    if issues:
        raise GroundingValidationError(issues)
