"""Deterministic explanation generation used by default and on every API failure."""

from __future__ import annotations

import re
from typing import Any

from .models import (
    EvidenceExplanation,
    GroundedExplanation,
    GuidelineExplanation,
    RetrievedGuidelineChunk,
)
from .retrieval import DIRECT_RULE_REFERENCE


_INTERPRETATIONS = {
    "ANOMALY": "The work is statistically unusual relative to its lifecycle comparison set.",
    "PEER_DEVIATION": "Observed values differ from robust peer benchmarks.",
    "DUPLICATE_REVIEW": "A corroborated Day-4.1 pair merits side-by-side verification.",
    "PAYMENT_EXECUTION": "Payment or fund-progress records contain review evidence.",
    "OBSERVED_CONDITIONS": "The source snapshot records an already-observed timing or cost condition.",
    "COMPLIANCE": "A deterministic Day-5 rule produced the stated compliance evidence.",
    "COST_OVERRUN_PREDICTION": "The weak prototype model supplies secondary early-warning rank context.",
    "OPERATIONAL_TREND_CONTEXT": "The work belongs to a group with supported operational trend deviation.",
}

_CAVEATS = {
    "ANOMALY": "An anomaly percentile is not a probability of wrongdoing.",
    "PEER_DEVIATION": "Peer deviation is statistical context, not a compliance conclusion.",
    "DUPLICATE_REVIEW": "The pair is a review candidate, not a confirmed duplicate.",
    "PAYMENT_EXECUTION": "The signal requires reconciliation with source records.",
    "OBSERVED_CONDITIONS": "Check approved revisions or extensions before drawing a conclusion.",
    "COMPLIANCE": "Only the cited deterministic rule result is reported; human review remains required.",
    "COST_OVERRUN_PREDICTION": "Held-out discrimination is weak and SHAP values are non-causal.",
    "OPERATIONAL_TREND_CONTEXT": "Aggregate trend context is not individual proof or a detector result.",
}

_STEPS = {
    "DUPLICATE_REVIEW": "Verify whether the paired sanction orders, locations, beneficiary or asset scope, and physical implementations describe distinct works.",
    "PAYMENT_EXECUTION": "Verify whether request, authorization, release, invoice, and PFMS/source records reconcile in their recorded sequence.",
    "COMPLIANCE": "Verify whether the document or field required by each cited deterministic rule is present and valid.",
    "OBSERVED_CONDITIONS": "Verify whether an approved extension, revised schedule, revised sanction, or authorized cost variation applies.",
    "ANOMALY": "Verify the unusual source values against the work file and lifecycle-comparable records.",
    "PEER_DEVIATION": "Verify whether legitimate work scope or local conditions explain the peer deviation.",
    "COST_OVERRUN_PREDICTION": "Use the early-warning rank only as secondary context and verify current approved costs and commitments.",
    "OPERATIONAL_TREND_CONTEXT": "Verify whether the aggregate operational change reflects reporting cadence, backlog clearance, or a substantive shift.",
}


def build_fallback_explanation(
    evidence_bundle: dict[str, Any],
    retrieved_chunks: list[RetrievedGuidelineChunk],
) -> GroundedExplanation:
    priority = evidence_bundle["review_priority"]
    why: list[EvidenceExplanation] = []
    for row in evidence_bundle["top_contributions"][:3]:
        family = str(row["family"])
        code = row.get("evidence_code")
        why.append(
            EvidenceExplanation(
                family=family,
                finding=str(row["evidence_summary"]),
                source_evidence_codes=[str(code)] if code else [],
                interpretation=_INTERPRETATIONS.get(
                    family, "This is existing deterministic review evidence."
                ),
                caveat=_CAVEATS.get(
                    family, "The evidence supports human review, not an automatic decision."
                ),
            )
        )

    compliance = evidence_bundle["compliance"]["actionable_findings"]
    guideline_context: list[GuidelineExplanation] = []
    for chunk in retrieved_chunks:
        matching = [
            row
            for row in compliance
            if chunk.chunk_id in row.get("guideline_chunk_ids", [])
        ]
        direct = chunk.retrieval_method == DIRECT_RULE_REFERENCE
        supported_clause = None
        if direct and matching:
            for clause in (
                item.strip()
                for item in str(matching[0]["guideline_clause"]).split(";")
            ):
                if clause in (chunk.clause_identifiers or "") or re.search(
                    rf"(?m)^\s*\*?{re.escape(clause)}\s", chunk.text
                ):
                    supported_clause = clause
                    break
        guideline_context.append(
            GuidelineExplanation(
                chunk_id=chunk.chunk_id,
                clause=supported_clause,
                page=chunk.page_start,
                relevance=(
                    "Direct reference from the stated deterministic Day-5 rule."
                    if direct
                    else "Semantic context only; it does not establish applicability or a compliance result."
                ),
            )
        )

    families = [item.family for item in why]
    steps = list(dict.fromkeys(_STEPS[family] for family in families if family in _STEPS))
    if not steps:
        steps = ["Verify the cited source evidence against the authorized work file."]
    limitations = [
        "Review priority is a prototype human-review policy score, not a probability or verdict.",
        "No specific compliance conclusion is established by analytical signals unless a cited deterministic Day-5 rule states one.",
        "Semantic guideline similarity is contextual retrieval, not proof of clause applicability.",
        "The source dataset is synthetic and external API availability is not required for this fallback.",
    ]
    prediction = evidence_bundle["prediction"]
    if prediction.get("cost_overrun_serving_score") is not None:
        limitations.append(
            "The cost-overrun model has prototype weak discrimination and is secondary evidence only."
        )
    if not prediction["delay_model"]["available"]:
        limitations.append("The delay predictive model is unavailable and supplies no model signal.")
    return GroundedExplanation(
        work_id=str(evidence_bundle["work_id"]),
        summary=(
            f"Work {evidence_bundle['work_id']} has {priority['review_priority_band']} "
            f"review priority at {float(priority['review_priority_score_0_100']):.3f}/100 "
            f"(overall rank {int(priority['review_priority_rank_overall'])})."
        ),
        why_flagged=why,
        guideline_context=guideline_context,
        verification_steps=steps,
        limitations=limitations,
        decision_statement=(
            "This review-support evidence does not establish fraud or wrongdoing; "
            "an authorized officer must verify source records before deciding what "
            "follow-up, if any, is warranted."
        ),
    )
