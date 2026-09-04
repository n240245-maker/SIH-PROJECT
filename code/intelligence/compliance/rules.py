"""Manually verified deterministic MPLADS compliance rules."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pandas as pd

from .guideline import GUIDELINE_VERSION, OFFICIAL_GUIDELINE_URL
from .models import (
    ComplianceResult,
    ComplianceRule,
    ComplianceSeverity,
    RuleContext,
    RuleOutcome,
    RuleSpec,
)


SANCTION_STAGES = ("EXECUTION", "COMPLETION")
COMPLETION_STAGES = ("COMPLETION",)


def _reference(pdf_page: int) -> str:
    return f"{OFFICIAL_GUIDELINE_URL}#page={pdf_page}"


def _result_semantics(review_reason: str) -> Mapping[str, str]:
    return {
        "PASS": "Available as-of evidence satisfies the encoded condition.",
        "REVIEW": review_reason,
        "NON_COMPLIANT": (
            "Available source fields directly contradict an explicit requirement "
            "without needing contextual interpretation."
        ),
        "NOT_APPLICABLE": (
            "The rule is outside the work lifecycle or its stated due point has "
            "not occurred by the controlled snapshot."
        ),
        "INSUFFICIENT_DATA": (
            "A required source value is absent, so no compliance conclusion is made."
        ),
    }


def _missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _timestamp(value: object) -> pd.Timestamp | None:
    if _missing(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def _active_assets(context: RuleContext) -> tuple[Mapping[str, Any], ...]:
    as_of = pd.Timestamp(context.as_of_date)
    return tuple(
        record
        for record in context.asset_records
        if (completion := _timestamp(record.get("completion_date"))) is not None
        and completion <= as_of
    )


def _outcome(
    result: ComplianceResult,
    observed: str,
    expected: str,
    evidence: str,
) -> RuleOutcome:
    return RuleOutcome(result, observed, expected, evidence)


def _sanction_response_45_days(context: RuleContext) -> RuleOutcome:
    recommendation = _timestamp(context.work.get("recommendation_date"))
    sanction = _timestamp(context.work.get("sanction_date_as_of"))
    expected = "Sanction/rejection response within 45 days, excluding model-code periods"
    if recommendation is None or sanction is None:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "recommendation or sanction date unavailable",
            expected,
            "Clause 3.2.4 timing cannot be calculated from the available dates.",
        )
    elapsed = int((sanction - recommendation).days)
    if 0 <= elapsed <= 45:
        return _outcome(
            ComplianceResult.PASS,
            f"{elapsed} calendar days",
            expected,
            "Observed elapsed time is within the 45-day outer band.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"{elapsed} calendar days",
        expected,
        "The 45-day band is exceeded or chronology is inconsistent; model-code exclusion periods are not available.",
    )


def _minimum_sanction_amount(context: RuleContext) -> RuleOutcome:
    amount = context.work.get("sanctioned_amount_inr")
    expected = "Individual sanctioned amount normally at least INR 250,000"
    if _missing(amount):
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "sanctioned amount unavailable",
            expected,
            "Clause 3.2.9 cannot be evaluated without the sanctioned amount.",
        )
    numeric = float(amount)
    if numeric >= 250_000:
        return _outcome(
            ComplianceResult.PASS,
            f"INR {numeric:.2f}",
            expected,
            "The sanctioned amount meets the normal minimum.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"INR {numeric:.2f}",
        expected,
        "A lower amount requires recorded public-benefit reasons, which are not present in the dataset.",
    )


def _sanction_completion_limit(context: RuleContext) -> RuleOutcome:
    sanction = _timestamp(context.work.get("sanction_date_as_of"))
    expected_completion = _timestamp(context.work.get("expected_completion_date"))
    expected = "Sanction-letter completion limit generally no more than one year"
    if sanction is None or expected_completion is None:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "sanction or expected-completion date unavailable",
            expected,
            "Clause 3.2.12 cannot be evaluated without both plan dates.",
        )
    days = int((expected_completion - sanction).days)
    if 0 <= days <= 365:
        return _outcome(
            ComplianceResult.PASS,
            f"{days} calendar days from sanction to expected completion",
            expected,
            "The recorded plan is within the guideline's general one-year band.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"{days} calendar days from sanction to expected completion",
        expected,
        "The plan exceeds the general band or has inconsistent chronology; exceptional-case justification is unavailable.",
    )


def _public_use_after_completion(context: RuleContext) -> RuleOutcome:
    assets = _active_assets(context)
    expected = "Every completed work put to public use as soon as completed"
    if not assets:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "no completed asset record available",
            expected,
            "Completion-stage asset evidence is missing.",
        )
    as_of = pd.Timestamp(context.as_of_date)
    visible = sum(
        (value := _timestamp(record.get("public_use_date"))) is not None
        and value <= as_of
        for record in assets
    )
    if visible == len(assets):
        return _outcome(
            ComplianceResult.PASS,
            f"{visible}/{len(assets)} asset records have public-use dates as of snapshot",
            expected,
            "All represented completed assets have visible public-use evidence.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"{visible}/{len(assets)} asset records have public-use dates as of snapshot",
        expected,
        "Public-use evidence is not yet visible for every completed asset; no fixed grace period is stated.",
    )


def _completion_photo(context: RuleContext) -> RuleOutcome:
    assets = _active_assets(context)
    expected = "Completed-work register contains photographs of the work"
    if not assets:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "no completed asset record available",
            expected,
            "Completion-stage asset evidence is missing.",
        )
    present = sum(
        not _missing(value := record.get("completion_photo_reference"))
        and bool(str(value).strip())
        for record in assets
    )
    if present == len(assets):
        return _outcome(
            ComplianceResult.PASS,
            f"{present}/{len(assets)} completed asset records contain photo references",
            expected,
            "Every represented completed work record contains a photo reference.",
        )
    return _outcome(
        ComplianceResult.NON_COMPLIANT,
        f"{present}/{len(assets)} completed asset records contain photo references",
        expected,
        "At least one completed-work record directly lacks the required photograph reference.",
    )


def _asset_handover(context: RuleContext) -> RuleOutcome:
    assets = _active_assets(context)
    expected = "Completed asset transferred to the User Agency without delay"
    if not assets:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "no completed asset record available",
            expected,
            "Completion-stage asset evidence is missing.",
        )
    as_of = pd.Timestamp(context.as_of_date)
    visible = sum(
        (value := _timestamp(record.get("handover_date"))) is not None
        and value <= as_of
        for record in assets
    )
    if visible == len(assets):
        return _outcome(
            ComplianceResult.PASS,
            f"{visible}/{len(assets)} handovers visible as of snapshot",
            expected,
            "All represented completed assets have visible handover evidence.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"{visible}/{len(assets)} handovers visible as of snapshot",
        expected,
        "Handover evidence is not visible for every completed asset; the clause gives no numeric grace period.",
    )


def _asset_register(context: RuleContext) -> RuleOutcome:
    assets = _active_assets(context)
    expected = "Transferred MPLADS asset entered in the applicable Asset Register"
    if not assets:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "no completed asset record available",
            expected,
            "Completion-stage asset evidence is missing.",
        )
    as_of = pd.Timestamp(context.as_of_date)
    handed_over = [
        record
        for record in assets
        if (value := _timestamp(record.get("handover_date"))) is not None
        and value <= as_of
    ]
    if not handed_over:
        return _outcome(
            ComplianceResult.NOT_APPLICABLE,
            "no handover visible as of snapshot",
            expected,
            "The encoded register-entry due point begins after transfer to the User Agency.",
        )
    raw_statuses = [record.get("asset_register_entry") for record in handed_over]
    if any(_missing(value) for value in raw_statuses):
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "asset-register status missing for at least one transferred asset",
            expected,
            "A required register-entry status is absent.",
        )
    statuses = [str(value).strip().casefold() for value in raw_statuses]
    if any(value == "no" for value in statuses):
        return _outcome(
            ComplianceResult.NON_COMPLIANT,
            ", ".join(statuses),
            expected,
            "A transferred asset is explicitly recorded as not entered in the Asset Register.",
        )
    if all(value == "yes" for value in statuses):
        return _outcome(
            ComplianceResult.PASS,
            f"{len(statuses)}/{len(statuses)} transferred assets recorded as entered",
            expected,
            "All transferred assets are recorded as entered in the Asset Register.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        ", ".join(statuses),
        expected,
        "At least one transferred asset has a pending or unrecognized register status.",
    )


def _completion_utilization_certificate(context: RuleContext) -> RuleOutcome:
    assets = _active_assets(context)
    expected = "Accounts finalized and Utilization Certificate furnished on completion"
    if not assets:
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "no completed asset record available",
            expected,
            "Completion-stage asset evidence is missing.",
        )
    statuses = [record.get("utilization_certificate_status") for record in assets]
    if any(_missing(value) for value in statuses):
        return _outcome(
            ComplianceResult.INSUFFICIENT_DATA,
            "utilization-certificate status missing",
            expected,
            "A required certificate status is absent.",
        )
    as_of = pd.Timestamp(context.as_of_date)
    visible = sum(
        str(record.get("utilization_certificate_status")).strip().casefold()
        == "submitted"
        and (value := _timestamp(record.get("utilization_certificate_date")))
        is not None
        and value <= as_of
        for record in assets
    )
    if visible == len(assets):
        return _outcome(
            ComplianceResult.PASS,
            f"{visible}/{len(assets)} certificates submitted as of snapshot",
            expected,
            "All represented completed assets have visible submitted-certificate evidence.",
        )
    return _outcome(
        ComplianceResult.REVIEW,
        f"{visible}/{len(assets)} certificates submitted as of snapshot; statuses="
        + ", ".join(str(value) for value in statuses),
        expected,
        "Certificate evidence is not visible for every completed asset; the clause uses 'quickly' without a numeric deadline.",
    )


IMPLEMENTED_RULES: tuple[ComplianceRule, ...] = (
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-3.2.4-SANCTION-45D",
            title="Recommendation response within 45 days",
            category="SANCTION",
            description="Checks the recorded recommendation-to-sanction interval.",
            lifecycle_stages=SANCTION_STAGES,
            severity=ComplianceSeverity.WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 3 - IMPLEMENTATION",
            guideline_clause="3.2.4; 3.2.6",
            guideline_page=19,
            guideline_printed_page="7",
            guideline_chunk_ids=("MPLADS-2023-P019",),
            official_reference=_reference(19),
            required_fields=(
                "features.lifecycle_stage",
                "features.recommendation_date",
                "features.sanction_date_as_of",
            ),
            evaluation_logic=(
                "PASS for 0-45 calendar days; REVIEW otherwise because model-code "
                "exclusion periods are unavailable."
            ),
            result_semantics=_result_semantics(
                "Timing needs review; excluded model-code periods are unavailable."
            ),
            test_coverage_identifier="test_rule_sanction_response_all_results",
        ),
        _sanction_response_45_days,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-3.2.9-MIN-SANCTION",
            title="Normal minimum sanctioned amount",
            category="SANCTION",
            description="Checks the guideline's normal INR 2.5 lakh minimum.",
            lifecycle_stages=SANCTION_STAGES,
            severity=ComplianceSeverity.INFO,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 3 - IMPLEMENTATION",
            guideline_clause="3.2.9",
            guideline_page=20,
            guideline_printed_page="8",
            guideline_chunk_ids=("MPLADS-2023-P020",),
            official_reference=_reference(20),
            required_fields=("features.lifecycle_stage", "features.sanctioned_amount_inr"),
            evaluation_logic=(
                "PASS at or above INR 250,000; REVIEW below because the clause "
                "allows a reasoned public-benefit exception."
            ),
            result_semantics=_result_semantics(
                "A sub-minimum sanction requires the recorded exception reason."
            ),
            test_coverage_identifier="test_rule_minimum_sanction_all_results",
        ),
        _minimum_sanction_amount,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-3.2.12-COMPLETION-LIMIT",
            title="General one-year completion limit",
            category="SANCTION",
            description="Checks the recorded sanction-to-expected-completion plan.",
            lifecycle_stages=SANCTION_STAGES,
            severity=ComplianceSeverity.WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 3 - IMPLEMENTATION",
            guideline_clause="3.2.12",
            guideline_page=20,
            guideline_printed_page="8",
            guideline_chunk_ids=("MPLADS-2023-P020",),
            official_reference=_reference(20),
            required_fields=(
                "features.lifecycle_stage",
                "features.sanction_date_as_of",
                "features.expected_completion_date",
            ),
            evaluation_logic=(
                "PASS for a 0-365 day sanction-to-plan interval; REVIEW otherwise "
                "because exceptional-case justification is unavailable."
            ),
            result_semantics=_result_semantics(
                "A longer plan requires the exceptional-case justification."
            ),
            test_coverage_identifier="test_rule_completion_limit_all_results",
        ),
        _sanction_completion_limit,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-3.2.17-PUBLIC-USE",
            title="Public use after completion",
            category="COMPLETION",
            description="Checks for visible public-use evidence for completed assets.",
            lifecycle_stages=COMPLETION_STAGES,
            severity=ComplianceSeverity.STRONG_WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 3 - IMPLEMENTATION",
            guideline_clause="3.2.17",
            guideline_page=21,
            guideline_printed_page="9",
            guideline_chunk_ids=("MPLADS-2023-P021",),
            official_reference=_reference(21),
            required_fields=(
                "features.lifecycle_stage",
                "assets.completion_date",
                "assets.public_use_date",
            ),
            evaluation_logic=(
                "PASS when every completed asset has public-use evidence by AS_OF_DATE; "
                "REVIEW otherwise because the clause states no numeric grace period."
            ),
            result_semantics=_result_semantics(
                "Public-use evidence is not visible for every completed asset."
            ),
            test_coverage_identifier="test_rule_public_use_all_results",
        ),
        _public_use_after_completion,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-4.5.3-COMPLETION-PHOTO",
            title="Completed-work photograph in register",
            category="COMPLETION",
            description="Checks for a photograph reference on completed-work records.",
            lifecycle_stages=COMPLETION_STAGES,
            severity=ComplianceSeverity.INFO,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 4 - MONITORING",
            guideline_clause="4.5.3",
            guideline_page=26,
            guideline_printed_page="14",
            guideline_chunk_ids=("MPLADS-2023-P026",),
            official_reference=_reference(26),
            required_fields=(
                "features.lifecycle_stage",
                "assets.completion_date",
                "assets.completion_photo_reference",
            ),
            evaluation_logic=(
                "PASS when every completed record has a photo reference; "
                "NON_COMPLIANT when an available completed record explicitly lacks it."
            ),
            result_semantics=_result_semantics(
                "A completed-work photo reference is absent."
            ),
            test_coverage_identifier="test_rule_completion_photo_all_results",
        ),
        _completion_photo,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-11.3-ASSET-HANDOVER",
            title="Completed asset handover",
            category="ASSET",
            description="Checks for visible transfer to the User Agency.",
            lifecycle_stages=COMPLETION_STAGES,
            severity=ComplianceSeverity.WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 11 - ACCOUNTING PROCEDURE",
            guideline_clause="11.3",
            guideline_page=51,
            guideline_printed_page="39",
            guideline_chunk_ids=("MPLADS-2023-P051",),
            official_reference=_reference(51),
            required_fields=(
                "features.lifecycle_stage",
                "assets.completion_date",
                "assets.handover_date",
            ),
            evaluation_logic=(
                "PASS when every completed asset has handover evidence by AS_OF_DATE; "
                "REVIEW otherwise because no numeric delay is specified."
            ),
            result_semantics=_result_semantics(
                "Handover evidence is not visible for every completed asset."
            ),
            test_coverage_identifier="test_rule_asset_handover_all_results",
        ),
        _asset_handover,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-4.5.8-ASSET-REGISTER",
            title="Transferred asset register entry",
            category="ASSET",
            description="Checks register status after an as-of-visible handover.",
            lifecycle_stages=COMPLETION_STAGES,
            severity=ComplianceSeverity.WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 4 / CHAPTER 11",
            guideline_clause="4.5.8; 11.3",
            guideline_page=26,
            guideline_printed_page="14; 39",
            guideline_chunk_ids=("MPLADS-2023-P026", "MPLADS-2023-P051"),
            official_reference=_reference(26),
            required_fields=(
                "features.lifecycle_stage",
                "assets.completion_date",
                "assets.handover_date",
                "assets.asset_register_entry",
            ),
            evaluation_logic=(
                "NOT_APPLICABLE before visible handover; PASS for Yes; REVIEW for "
                "Pending/unknown; NON_COMPLIANT for an explicit No after handover."
            ),
            result_semantics=_result_semantics(
                "A transferred asset has a pending or unrecognized register status."
            ),
            test_coverage_identifier="test_rule_asset_register_all_results",
        ),
        _asset_register,
    ),
    ComplianceRule(
        RuleSpec(
            rule_id="MPLADS-11.2-COMPLETION-UC",
            title="Utilization Certificate on completion",
            category="UTILIZATION_CERTIFICATE",
            description="Checks for visible submitted-certificate evidence after completion.",
            lifecycle_stages=COMPLETION_STAGES,
            severity=ComplianceSeverity.STRONG_WARNING,
            guideline_version=GUIDELINE_VERSION,
            guideline_chapter="CHAPTER 11 - ACCOUNTING PROCEDURE",
            guideline_clause="11.2",
            guideline_page=51,
            guideline_printed_page="39",
            guideline_chunk_ids=("MPLADS-2023-P051",),
            official_reference=_reference(51),
            required_fields=(
                "features.lifecycle_stage",
                "assets.completion_date",
                "assets.utilization_certificate_status",
                "assets.utilization_certificate_date",
            ),
            evaluation_logic=(
                "PASS when every completed asset has a Submitted certificate dated by "
                "AS_OF_DATE; REVIEW otherwise because 'quickly' is not a numeric deadline."
            ),
            result_semantics=_result_semantics(
                "Utilization-certificate evidence is not visible for every completed asset."
            ),
            test_coverage_identifier="test_rule_completion_uc_all_results",
        ),
        _completion_utilization_certificate,
    ),
)


IMPLEMENTED_RULE_BY_ID = {rule.spec.rule_id: rule for rule in IMPLEMENTED_RULES}
if len(IMPLEMENTED_RULE_BY_ID) != len(IMPLEMENTED_RULES):
    raise RuntimeError("Compliance rule IDs must be unique")
