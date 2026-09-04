"""Small transparent data model for deterministic compliance rules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class ComplianceResult(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ComplianceSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    STRONG_WARNING = "STRONG_WARNING"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    rule_id: str
    title: str
    category: str
    description: str
    lifecycle_stages: tuple[str, ...]
    severity: ComplianceSeverity
    guideline_version: str
    guideline_chapter: str
    guideline_clause: str
    guideline_page: int
    guideline_printed_page: str
    guideline_chunk_ids: tuple[str, ...]
    official_reference: str
    required_fields: tuple[str, ...]
    evaluation_logic: str
    result_semantics: Mapping[str, str]
    test_coverage_identifier: str


@dataclass(frozen=True, slots=True)
class RuleContext:
    work: Mapping[str, Any]
    asset_records: tuple[Mapping[str, Any], ...]
    as_of_date: date


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    result: ComplianceResult
    observed_value: str
    expected_condition: str
    evidence: str


RuleEvaluator = Callable[[RuleContext], RuleOutcome]


@dataclass(frozen=True, slots=True)
class ComplianceRule:
    spec: RuleSpec
    evaluate: RuleEvaluator
