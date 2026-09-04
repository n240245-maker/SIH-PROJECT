"""Auditable implemented-rule and deferred-candidate registry."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any

from .guideline import GUIDELINE_VERSION, OFFICIAL_GUIDELINE_URL
from .models import ComplianceRule
from .rules import IMPLEMENTED_RULES


def _source(pdf_page: int) -> str:
    return f"{OFFICIAL_GUIDELINE_URL}#page={pdf_page}"


UNIMPLEMENTED_RULE_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "CANDIDATE-3.2.3-FULL-ESTIMATE-CONSENT",
        "title": "Full estimate consent and allocation",
        "category": "SANCTION",
        "description": "Potential check when an estimate exceeds the MP-indicated amount.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 3 - IMPLEMENTATION",
        "guideline_clause": "3.2.3",
        "guideline_page": 19,
        "guideline_printed_page": "7",
        "guideline_chunk_ids": ["MPLADS-2023-P019"],
        "official_reference": _source(19),
        "required_fields": [
            "technical_estimate_amount_inr",
            "recommended_amount_inr",
            "mp_full_estimate_consent",
            "allocated_full_estimate_amount",
        ],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "MP consent and allocation evidence are not present.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-3.2.7-O_AND_M-UNDERTAKING",
        "title": "Pre-sanction operation and maintenance undertaking",
        "category": "SANCTION",
        "description": "Potential check for the User Agency's written undertaking.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 3 - IMPLEMENTATION",
        "guideline_clause": "3.2.7",
        "guideline_page": 19,
        "guideline_printed_page": "7",
        "guideline_chunk_ids": ["MPLADS-2023-P019"],
        "official_reference": _source(19),
        "required_fields": ["operation_maintenance_undertaking_reference"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "The written undertaking is not represented in source data.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-3.2.8-STATUTORY-CLEARANCES",
        "title": "Pre-sanction statutory and regulatory clearances",
        "category": "SANCTION",
        "description": "Potential check that applicable clearances preceded sanction.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "STRONG_WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 3 - IMPLEMENTATION",
        "guideline_clause": "3.2.8",
        "guideline_page": 20,
        "guideline_printed_page": "8",
        "guideline_chunk_ids": ["MPLADS-2023-P020"],
        "official_reference": _source(20),
        "required_fields": ["required_clearances", "clearance_dates", "sanction_date"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "Applicable clearance types and dated documents are absent.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-3.2.13-OPEN-BIDDING",
        "title": "Open and transparent vendor selection",
        "category": "EXECUTION",
        "description": "Potential check of the work-level procurement process.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "STRONG_WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 3 - IMPLEMENTATION",
        "guideline_clause": "3.2.13",
        "guideline_page": 20,
        "guideline_printed_page": "8",
        "guideline_chunk_ids": ["MPLADS-2023-P020"],
        "official_reference": _source(20),
        "required_fields": ["tender_reference", "bid_publication", "bid_evaluation"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "Tender and bid-process documents are absent.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-4.5.2-DISTRICT-INSPECTION",
        "title": "Annual district inspection coverage",
        "category": "AUDIT",
        "description": "Potential annual check of the district's 10 percent inspection duty.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 4 - MONITORING",
        "guideline_clause": "4.5.2",
        "guideline_page": 26,
        "guideline_printed_page": "14",
        "guideline_chunk_ids": ["MPLADS-2023-P026"],
        "official_reference": _source(26),
        "required_fields": ["district_year_work_universe", "district_inspection_register"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "No district-year inspection register or denominator exists.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-4.6.2-AGENCY-INSPECTION",
        "title": "Implementing Agency inspection coverage",
        "category": "AUDIT",
        "description": "Potential check that the Implementing Agency inspected every work.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 4 - MONITORING",
        "guideline_clause": "4.6.2",
        "guideline_page": 27,
        "guideline_printed_page": "15",
        "guideline_chunk_ids": ["MPLADS-2023-P027"],
        "official_reference": _source(27),
        "required_fields": ["implementing_agency_site_visit_register"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "Work-site visit and inspection-register evidence is absent.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-5.1.1-DURABLE-PUBLIC-ASSET",
        "title": "Durable public asset and unrestricted access",
        "category": "ELIGIBILITY",
        "description": "Potential eligibility check for durable public-good assets.",
        "lifecycle_applicability": ["PRE_SANCTION", "EXECUTION", "COMPLETION"],
        "severity": "STRONG_WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 5 - PERMISSIBLE WORKS",
        "guideline_clause": "5.1.1; 5.1.2",
        "guideline_page": 28,
        "guideline_printed_page": "16",
        "guideline_chunk_ids": ["MPLADS-2023-P028"],
        "official_reference": _source(28),
        "required_fields": ["land_ownership", "institution_control", "access_restrictions"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": (
            "Descriptions and broad asset types cannot establish land ownership, "
            "institutional control, durability, or unrestricted access."
        ),
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-11.4.1-PAYMENT-UC",
        "title": "Utilization Certificate for each vendor payment",
        "category": "UTILIZATION_CERTIFICATE",
        "description": "Potential payment-level certificate linkage check.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "STRONG_WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 11 - ACCOUNTING PROCEDURE",
        "guideline_clause": "11.4.1",
        "guideline_page": 51,
        "guideline_printed_page": "39",
        "guideline_chunk_ids": ["MPLADS-2023-P051"],
        "official_reference": _source(51),
        "required_fields": ["payment_id", "payment_utilization_certificate_reference"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": "The source has only work-level UC status, not payment-level linkage.",
        "test_coverage_identifier": None,
    },
    {
        "rule_id": "CANDIDATE-11.4.4-ANNUAL-AUDIT-DEADLINE",
        "title": "Annual audit report deadline",
        "category": "AUDIT",
        "description": "Potential authority-level September 30 audit deadline check.",
        "lifecycle_applicability": ["EXECUTION", "COMPLETION"],
        "severity": "STRONG_WARNING",
        "guideline_version": GUIDELINE_VERSION,
        "guideline_chapter": "CHAPTER 11 - ACCOUNTING PROCEDURE",
        "guideline_clause": "11.4.4",
        "guideline_page": 51,
        "guideline_printed_page": "39",
        "guideline_chunk_ids": ["MPLADS-2023-P051"],
        "official_reference": _source(51),
        "required_fields": ["fund_release_financial_year", "authority_audit_report_date"],
        "evaluation_logic": None,
        "result_semantics": None,
        "implemented_status": "UNIMPLEMENTED_RULE_CANDIDATE",
        "unimplemented_reason": (
            "Work-level audit dates are not linked to fund-release year or the "
            "responsible authority's annual report."
        ),
        "test_coverage_identifier": None,
    },
)


def implemented_rule_entry(rule: ComplianceRule) -> dict[str, Any]:
    spec = rule.spec
    return {
        "rule_id": spec.rule_id,
        "title": spec.title,
        "category": spec.category,
        "description": spec.description,
        "lifecycle_applicability": list(spec.lifecycle_stages),
        "severity": spec.severity.value,
        "guideline_version": spec.guideline_version,
        "guideline_chapter": spec.guideline_chapter,
        "guideline_clause": spec.guideline_clause,
        "guideline_page": spec.guideline_page,
        "guideline_printed_page": spec.guideline_printed_page,
        "guideline_chunk_ids": list(spec.guideline_chunk_ids),
        "official_reference": spec.official_reference,
        "required_fields": list(spec.required_fields),
        "evaluation_logic": spec.evaluation_logic,
        "result_semantics": dict(spec.result_semantics),
        "implemented_status": "IMPLEMENTED",
        "unimplemented_reason": None,
        "test_coverage_identifier": spec.test_coverage_identifier,
    }


def build_rule_registry(
    rules: Iterable[ComplianceRule] = IMPLEMENTED_RULES,
) -> dict[str, Any]:
    implemented = [implemented_rule_entry(rule) for rule in rules]
    all_rules = [*implemented, *UNIMPLEMENTED_RULE_CANDIDATES]
    ids = [record["rule_id"] for record in all_rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Compliance registry contains duplicate rule IDs")
    return {
        "guideline_version": GUIDELINE_VERSION,
        "implemented_rule_count": len(implemented),
        "unimplemented_candidate_count": len(UNIMPLEMENTED_RULE_CANDIDATES),
        "rules": all_rules,
    }


def write_rule_registry(path: str | Path) -> Path:
    destination = Path(path)
    destination.write_text(
        json.dumps(build_rule_registry(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
