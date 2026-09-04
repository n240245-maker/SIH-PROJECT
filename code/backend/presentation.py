"""Officer-facing presentation facts derived only from governed work evidence."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


FAMILY_LABELS = {
    "ANOMALY": "Unusual Pattern Detection",
    "PEER_DEVIATION": "Peer Comparison",
    "DUPLICATE_REVIEW": "Duplicate Work Review",
    "PAYMENT_EXECUTION": "Payments & Fund-Progress",
    "OBSERVED_CONDITIONS": "Observed Cost / Delay Conditions",
    "COMPLIANCE": "MPLADS Compliance Monitoring",
    "COST_PREDICTION": "Cost-Overrun Early Warning",
    "OPERATIONAL_TREND_CONTEXT": "Operational Trend Context",
}

PEER_METRIC_LABELS = {
    "days_since_last_payment_as_of": "Time since latest payment",
    "estimate_to_recommended_ratio": "Technical estimate vs recommended amount",
    "expected_minus_physical_gap_pct_as_of": "Expected vs physical progress gap",
    "expenditure_to_sanction_pct_as_of": "Released payments as share of sanction",
    "financial_minus_physical_gap_pct_as_of": "Financial vs physical progress gap",
    "financial_overrun_pct_as_of": "Amount above sanction",
    "largest_payment_share_as_of": "Largest single payment share",
    "latest_financial_progress_pct_as_of": "Latest reported financial progress",
    "latest_physical_progress_pct_as_of": "Latest reported physical progress",
    "max_physical_progress_drop_pct_as_of": "Largest recorded physical progress decrease",
    "overdue_days_as_of": "Observed overdue days",
    "physical_progress_decrease_count_as_of": "Recorded physical progress decreases",
    "physical_progress_velocity_pct_per_30d": "Physical progress pace",
    "recommended_amount_inr": "Recommended amount",
    "released_payment_total_inr_as_of": "Released payments",
    "sanction_to_estimate_ratio": "Sanction vs technical estimate",
    "sanction_to_recommended_ratio": "Sanction vs recommended amount",
    "sanctioned_amount_inr": "Sanctioned amount",
    "schedule_elapsed_ratio_as_of": "Share of planned schedule elapsed",
    "technical_estimate_amount_inr": "Technical estimate",
    "progress_report_count": "Progress reports recorded",
    "released_payment_amount_inr": "Released payment amount",
    "released_payment_count": "Released payment count",
}


def friendly_metric_label(value: Any) -> str:
    key = str(value or "")
    return PEER_METRIC_LABELS.get(key, "Peer comparison metric")


def humanize_narrative(value: Any) -> str:
    rendered = str(value or "")
    observed_pattern = re.compile(
        r"Observed overdue=(True|False) \(days=(-?\d+(?:\.\d+)?), score=(-?\d+(?:\.\d+)?)\); "
        r"observed over sanction=(True|False) \(overrun_pct=(-?\d+(?:\.\d+)?), score=(-?\d+(?:\.\d+)?)\)\."
    )
    rendered = observed_pattern.sub(
        lambda match: (
            f"Observed overdue: {'Yes' if match.group(1) == 'True' else 'No'} "
            f"({float(match.group(2)):.1f} days; review score {float(match.group(3)):.1f}). "
            f"Observed above sanction: {'Yes' if match.group(4) == 'True' else 'No'} "
            f"({float(match.group(5)):.1f}%; review score {float(match.group(6)):.1f})."
        ),
        rendered,
    )
    replacements = {
        **PEER_METRIC_LABELS,
        **FAMILY_LABELS,
        "PERSISTENT_FUND_PROGRESS_REVIEW": "Persistent financial-vs-physical progress mismatch",
        "CURRENT_LARGE_POSITIVE_FUND_GAP": "Current financial-vs-physical progress mismatch",
        "OBSERVED_OVER_SANCTION": "Observed amount above sanction",
        "OBSERVED_OVERDUE": "Observed overdue condition",
        "LIFECYCLE_ANOMALY_PERCENTILE": "Within-lifecycle unusualness",
        "STATISTICAL_PEER_OUTLIER": "Unusual peer comparison",
        "PAYMENT_AUTH_BEFORE_REQUEST": "authorization recorded before request",
        "REVIEW/STRONG_WARNING": "review / strong warning",
    }
    for key in sorted(replacements, key=len, reverse=True):
        rendered = rendered.replace(key, replacements[key])
    rendered = re.sub(r"-?\d+\.\d{2,}", lambda match: f"{float(match.group(0)):.1f}", rendered)
    return rendered


def friendly_group(value: Any) -> str:
    rendered = str(value or "Not available")
    for source, label in (("state_name=", "State: "), ("district=", "District: "), ("sector=", "Sector: ")):
        rendered = rendered.replace(source, label)
    return rendered.replace("|", "; ")

ALERT_LABELS = {
    "COMPLIANCE_REVIEW": "MPLADS rule requires verification",
    "COST_OVERRUN_EARLY_WARNING": "Cost-overrun early warning",
    "DETERMINISTIC_NON_COMPLIANCE": "Deterministic non-compliance",
    "DUPLICATE_REVIEW_CANDIDATE": "Possible duplicate work requires comparison",
    "FUND_PROGRESS_REVIEW": "Financial and physical progress require reconciliation",
    "OBSERVED_OVERDUE": "Work is already overdue",
    "OBSERVED_OVER_SANCTION": "Released payments exceed the visible sanction",
    "OPERATIONAL_TREND_DEVIATION": "Unusual surrounding operational trend",
    "PAYMENT_IRREGULARITY": "Payment record requires verification",
    "PEER_DEVIATION": "Work differs from similar works",
    "STATISTICAL_ANOMALY": "Unusual within-lifecycle pattern",
}

ALERT_ACTIONS = {
    "COMPLIANCE_REVIEW": "Verify the cited rule, source documents, and any permitted exception.",
    "DETERMINISTIC_NON_COMPLIANCE": "Verify the authoritative register and cited guideline requirement.",
    "DUPLICATE_REVIEW_CANDIDATE": "Compare the paired work files, location, amounts, dates, and implementing agencies.",
    "FUND_PROGRESS_REVIEW": "Reconcile expenditure records with physical progress reports and work completed.",
    "OBSERVED_OVERDUE": "Verify the approved completion schedule and any authorized extension.",
    "OBSERVED_OVER_SANCTION": "Check the original sanction and any approved revised sanction or cost variation.",
    "PAYMENT_IRREGULARITY": "Verify the payment request, authorization order, and PFMS/source sequence.",
    "PEER_DEVIATION": "Compare the source value with lifecycle-similar works and verify the work file.",
    "STATISTICAL_ANOMALY": "Verify unusual source values against the work file; this is not a finding.",
    "COST_OVERRUN_EARLY_WARNING": "Use only as secondary context and verify current cost records.",
    "OPERATIONAL_TREND_DEVIATION": "Use as surrounding context; do not treat it as direct evidence against this work.",
}

ACTIONABLE_ALERT_TYPES = frozenset({
    "COMPLIANCE_REVIEW",
    "DETERMINISTIC_NON_COMPLIANCE",
    "DUPLICATE_REVIEW_CANDIDATE",
    "FUND_PROGRESS_REVIEW",
    "OBSERVED_OVERDUE",
    "OBSERVED_OVER_SANCTION",
    "PAYMENT_IRREGULARITY",
})

ATTENTION_LEVEL_LABELS = {
    "NORMAL": "Normal",
    "LOW_ATTENTION": "Low Attention",
    "MEDIUM_ATTENTION": "Medium Attention",
    "HIGH_ATTENTION": "High Attention",
    "IMMEDIATE_PRIORITY": "Immediate Priority",
}

DOCUMENT_RULES = {
    "utilization_certificate": "MPLADS-11.2-COMPLETION-UC",
    "handover": "MPLADS-11.3-ASSET-HANDOVER",
    "public_use": "MPLADS-3.2.17-PUBLIC-USE",
    "completed_work_photograph": "MPLADS-4.5.3-COMPLETION-PHOTO",
    "asset_register": "MPLADS-4.5.8-ASSET-REGISTER",
}

REVIEW_NOTE = (
    "This assessment is intended to support authorized human review. It summarizes "
    "recorded project data, deterministic MPLADS rule checks and analytical signals. "
    "The observations do not by themselves establish fraud, misuse, corruption or wrongdoing. "
    "Any administrative, financial or legal conclusion must be based on verification of "
    "authoritative records, approved revisions and applicable procedures."
)


def is_actionable_alert(alert_type: Any) -> bool:
    return str(alert_type or "") in ACTIONABLE_ALERT_TYPES


def requires_review_from_alerts(alerts: list[dict[str, Any]]) -> bool:
    return any(is_actionable_alert(item.get("alert_type")) for item in alerts)


def attention_level_from_band(band: Any, requires_review: bool) -> str:
    value = str(band or "").upper()
    if value == "CRITICAL":
        return "IMMEDIATE_PRIORITY"
    if value == "HIGH":
        return "HIGH_ATTENTION"
    if value == "MEDIUM":
        return "MEDIUM_ATTENTION"
    return "LOW_ATTENTION" if requires_review else "NORMAL"


def financial_exceedance_display_severity(
    percentage_above_sanction: Any, *, observed: bool
) -> dict[str, str]:
    value = _number(percentage_above_sanction)
    if not observed or value is None or value <= 0:
        return {"code": "NORMAL", "label": "Normal", "state": "pass"}
    if value <= 5:
        return {"code": "LOW_ATTENTION", "label": "Low Attention", "state": "review"}
    if value <= 15:
        return {"code": "REQUIRES_REVIEW", "label": "Requires Review", "state": "review"}
    if value <= 30:
        return {"code": "HIGH_ATTENTION", "label": "High Attention", "state": "review"}
    return {"code": "VERY_HIGH_ATTENTION", "label": "Very High Attention", "state": "strong_issue"}


def _friendly_date(value: Any) -> str:
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return str(value or "Not available")
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def _money_text(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Not available"
    absolute = abs(number)
    if absolute >= 10_000_000:
        return f"INR {number / 10_000_000:.2f} crore"
    if absolute >= 100_000:
        return f"INR {number / 100_000:.2f} lakh"
    return f"INR {number:,.0f}"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def _truth(value: Any) -> bool:
    return value is True or str(value).casefold() in {"true", "1", "yes"}


def _payment_dates(evidence: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for item in evidence:
        if item.get("signal_code") != "PAYMENT_AUTH_BEFORE_REQUEST":
            continue
        observed = str(item.get("observed_value") or "")
        auth = re.search(r"authorization=(\d{4}-\d{2}-\d{2})", observed)
        request = re.search(r"request=(\d{4}-\d{2}-\d{2})", observed)
        return (auth.group(1) if auth else None, request.group(1) if request else None)
    return None, None


def _alert_semantics(alert_type: str) -> tuple[str, str]:
    if alert_type in {"OBSERVED_OVERDUE", "OBSERVED_OVER_SANCTION", "DETERMINISTIC_NON_COMPLIANCE"}:
        return "Observed Condition" if alert_type != "DETERMINISTIC_NON_COMPLIANCE" else "Compliance Review", "strong_issue"
    if alert_type == "DUPLICATE_REVIEW_CANDIDATE":
        return "Analytical Signal", "review"
    if alert_type in {"COMPLIANCE_REVIEW", "FUND_PROGRESS_REVIEW", "PAYMENT_IRREGULARITY"}:
        return "Compliance Review" if alert_type == "COMPLIANCE_REVIEW" else "Observed Condition", "review"
    if alert_type == "OPERATIONAL_TREND_DEVIATION":
        return "Operational Context", "context"
    return "Analytical Signal", "analytical"


def build_work_presentation(detail: dict[str, Any]) -> dict[str, Any]:
    """Build safe display facts; this function never creates detection logic."""

    profile = detail["profile"]
    payments = detail["payments"]
    payment_evidence = list(payments.get("evidence") or [])
    fund = payments.get("fund_progress") or {}
    compliance_rules = list(detail["compliance"].get("rules") or [])
    compliance_by_id = {str(rule.get("rule_id")): rule for rule in compliance_rules}
    alerts = list(detail.get("alerts") or [])
    alert_types = {str(item.get("alert_type")) for item in alerts}
    payment_codes = {str(item.get("signal_code")) for item in payment_evidence}
    lifecycle = str(profile.get("lifecycle_stage") or "")

    sanction = _number(profile.get("sanctioned_amount_inr"))
    released = _number(profile.get("released_payment_total_inr_as_of"))
    difference = released - sanction if sanction is not None and released is not None else None
    above_pct = max(0.0, difference / sanction * 100) if difference is not None and sanction not in {None, 0} else None
    physical = _number(profile.get("latest_physical_progress_pct_as_of"))
    financial = _number(profile.get("latest_financial_progress_pct_as_of"))
    gap = financial - physical if financial is not None and physical is not None else None
    persistent_gap = _truth(fund.get("persistent_large_reported_gap_review_heuristic"))
    authorization_date, request_date = _payment_dates(payment_evidence)
    observed_over_sanction = "RELEASED_TOTAL_EXCEEDS_SANCTION" in payment_codes
    exceedance_severity = financial_exceedance_display_severity(
        above_pct, observed=observed_over_sanction
    )
    requires_review = requires_review_from_alerts(alerts)
    attention_level = attention_level_from_band(
        (detail.get("priority") or {}).get("review_priority_band"), requires_review
    )

    peers = list((detail.get("peer_benchmark") or {}).get("top_deviations") or [])
    peer_outliers = [
        row for row in peers if _truth(row.get("statistical_peer_outlier"))
    ]
    peer_comparisons = []
    for row in sorted(
        peer_outliers,
        key=lambda item: abs(_number(item.get("robust_deviation")) or 0),
        reverse=True,
    ):
        direction = str(row.get("direction") or "")
        comparison = (
            "Far above similar works"
            if direction == "ABOVE_PEERS"
            else "Far below similar works"
            if direction == "BELOW_PEERS"
            else "Markedly different from similar works"
        )
        peer_comparisons.append({
            "metric": row.get("metric"),
            "label": friendly_metric_label(row.get("metric")),
            "observed_value": row.get("observed_value"),
            "peer_median": row.get("peer_median"),
            "comparison": comparison,
            "peer_group_size": row.get("peer_group_size"),
            "why_it_matters": (
                f"This work differs substantially from comparable works on "
                f"{friendly_metric_label(row.get('metric')).lower()}."
            ),
            "technical": row,
        })

    trend = detail.get("trend_context") or {}
    trend_detail = trend.get("display_detail") or {}
    trend_z = _number(trend.get("strongest_operational_trend_robust_z"))
    trend_flag = _truth(trend.get("operational_trend_deviation_flag"))
    trend_assessment = "No strong surrounding trend deviation is currently flagged."
    if trend_flag and trend_z is not None:
        trend_assessment = (
            "Much higher than the recent historical pattern"
            if trend_z > 0
            else "Much lower than the recent historical pattern"
        )
    trend_presentation = {
        "title": f"Recent {friendly_metric_label(trend.get('strongest_operational_trend_metric')).lower()}",
        "group": friendly_group(trend.get("selected_trend_group_value")),
        "metric": trend.get("strongest_operational_trend_metric"),
        "current_month": trend_detail.get("month"),
        "current_value": trend_detail.get("current_value"),
        "baseline_value": trend_detail.get("median"),
        "assessment": trend_assessment,
        "has_supported_deviation": trend_flag,
        "technical": {
            "robust_deviation": trend_z,
            "baseline_month_count": trend_detail.get("baseline_month_count"),
            "historical_event_support": trend_detail.get("historical_event_support"),
            "group_token": trend.get("selected_trend_group_value"),
        },
    }

    warning_signals = []
    for alert in alerts:
        alert_type = str(alert.get("alert_type") or "")
        category, state = _alert_semantics(alert_type)
        title = ALERT_LABELS.get(alert_type, alert_type.replace("_", " ").title())
        summary = "This governed signal requires review of the linked source record."
        key_facts: list[dict[str, Any]] = []
        severity_label = {
            "strong_issue": "High Attention",
            "review": "Requires Review",
            "analytical": "Analytical Signal",
            "context": "Operational Context",
        }.get(state, "Information")
        why = "This governed signal helps prioritize human review; it is not a verdict."

        if alert_type == "OBSERVED_OVER_SANCTION":
            title = "Released payments are above the visible sanction"
            state = exceedance_severity["state"]
            severity_label = exceedance_severity["label"]
            summary = (
                f"{_money_text(released)} released against {_money_text(sanction)} sanctioned; "
                f"the recorded difference is {_money_text(difference)} ({above_pct:.1f}% above sanction)."
            )
            key_facts = [
                {"label": "Released payments", "value": released, "format": "currency"},
                {"label": "Sanctioned amount", "value": sanction, "format": "currency"},
                {"label": "Recorded difference", "value": difference, "format": "currency"},
            ]
            why = (
                "The released amount is slightly above the visible sanction and may have an administrative explanation."
                if above_pct is not None and above_pct <= 5
                else "The released amount is materially above the visible sanction and needs source-record verification."
            )
        elif alert_type == "FUND_PROGRESS_REVIEW":
            title = "Financial progress is ahead of physical progress"
            if gap is not None:
                direction = "ahead of" if gap >= 0 else "behind"
                summary = (
                    f"Financial progress is {abs(gap):.1f} percentage points {direction} reported physical progress."
                )
                if persistent_gap:
                    summary += " This mismatch appears across multiple consecutive progress reports."
            key_facts = [
                {"label": "Physical progress", "value": physical, "format": "percent"},
                {"label": "Financial progress", "value": financial, "format": "percent"},
                {"label": "Progress difference", "value": gap, "format": "percentage_points"},
            ]
        elif alert_type == "PAYMENT_IRREGULARITY" and authorization_date and request_date:
            title = "Payment chronology needs verification"
            summary = (
                f"Authorization is recorded on {_friendly_date(authorization_date)}, before the request dated "
                f"{_friendly_date(request_date)}."
            )
            key_facts = [
                {"label": "Authorization", "value": authorization_date, "format": "date"},
                {"label": "Request", "value": request_date, "format": "date"},
            ]
        elif alert_type == "OBSERVED_OVERDUE":
            days = _number(profile.get("overdue_days_as_of"))
            title = "Completion schedule requires attention"
            summary = (
                f"Completion is not recorded as of {_friendly_date(profile.get('feature_snapshot_date'))}; "
                f"the work is {days:.0f} days past the expected completion date."
                if days is not None
                else "The expected completion date has passed and completion is not recorded."
            )
            key_facts = [
                {"label": "Expected completion", "value": profile.get("expected_completion_date"), "format": "date"},
                {"label": "Analytical snapshot", "value": profile.get("feature_snapshot_date"), "format": "date"},
                {"label": "Observed overdue period", "value": days, "format": "days"},
            ]
        elif alert_type in {"COMPLIANCE_REVIEW", "DETERMINISTIC_NON_COMPLIANCE"}:
            rule = compliance_by_id.get(str(alert.get("evidence_code"))) or {}
            result = str(rule.get("result") or "REVIEW")
            title = str(rule.get("rule_title") or ALERT_LABELS.get(alert_type))
            severity_label = "Non-Compliant" if result == "NON_COMPLIANT" else "Requires Review"
            state = "strong_issue" if result == "NON_COMPLIANT" else "review"
            summary = (
                f"The deterministic rule check recorded {severity_label.lower()}. "
                f"Observed: {rule.get('observed_value') or 'Not available'}."
            )
            key_facts = [
                {"label": "Recorded result", "value": severity_label, "format": "text"},
                {"label": "Expected condition", "value": rule.get("expected_condition"), "format": "text"},
            ]
            why = "The result comes from the existing deterministic MPLADS rule engine."
        elif alert_type == "DUPLICATE_REVIEW_CANDIDATE":
            title = "A possible duplicate work needs comparison"
            candidate = ((detail.get("duplicates") or {}).get("review_candidates") or [{}])[0]
            paired = candidate.get("paired_work") or {}
            summary = (
                f"The existing corroborated candidate policy linked this work with "
                f"{paired.get('work_id') or 'another recorded work'} for side-by-side review."
            )
            key_facts = [
                {"label": "Candidate work", "value": paired.get("work_id"), "format": "text"},
                {"label": "Comparison score", "value": candidate.get("duplicate_similarity_score_0_100"), "format": "score"},
            ]
        elif alert_type == "STATISTICAL_ANOMALY":
            percentile = _number((detail.get("anomaly") or {}).get("within_stage_anomaly_percentile_0_100"))
            title = "Highly unusual compared with similar-stage works"
            summary = (
                f"This work is more statistically unusual than about {percentile:.1f}% of works at the same lifecycle stage."
                if percentile is not None
                else "This work has an existing within-stage analytical unusualness signal."
            )
            why = "This is an analytical review signal, not a probability of wrongdoing."
        elif alert_type == "PEER_DEVIATION":
            title = "Strong differences from similar works"
            if peer_comparisons:
                first = peer_comparisons[0]
                summary = f"{first['label']}: {first['comparison'].lower()}."
            else:
                summary = "An existing peer-comparison signal is present."
            why = "The comparison identifies unusual recorded values; it does not establish a violation."
        elif alert_type == "OPERATIONAL_TREND_DEVIATION":
            title = "Most unusual surrounding operational trend"
            summary = f"{trend_presentation['title']}: {trend_presentation['assessment'].lower()}."
            why = "This describes the surrounding operational environment, not direct evidence against this work."
        elif alert_type == "COST_OVERRUN_EARLY_WARNING":
            title = "Cost-overrun early warning"
            summary = "A limited-reliability model provides secondary early-warning context."
            why = "The model output is secondary evidence and is not a finding or causal explanation."
        else:
            summary = humanize_narrative(alert.get("alert_summary"))

        warning_signals.append({
            "category": category,
            "state": state,
            "severity_label": severity_label,
            "title": title,
            "summary": summary,
            "key_facts": key_facts,
            "why_attention": why,
            "officer_verification": ALERT_ACTIONS.get(alert_type, "Verify the linked source evidence."),
            "technical_reference": {
                "alert_type": alert_type,
                "evidence_code": alert.get("evidence_code"),
                "source_artifact": alert.get("source_artifact"),
                "source_record_reference": alert.get("source_record_reference"),
                "original_summary": alert.get("alert_summary"),
            },
        })

    highlights: dict[str, dict[str, str]] = {}
    if observed_over_sanction:
        highlights["released_payment_total_inr_as_of"] = {
            "state": exceedance_severity["state"],
            "label": exceedance_severity["label"],
            "reason": "Released payments exceed the visible sanctioned amount.",
        }
    if "FUND_PROGRESS_REVIEW" in alert_types:
        for field in (
            "latest_financial_progress_pct_as_of",
            "latest_physical_progress_pct_as_of",
            "financial_minus_physical_gap_pct_as_of",
        ):
            highlights[field] = {
                "state": "review",
                "label": "Requires Review",
                "reason": "Existing fund-progress evidence requires reconciliation.",
            }
    if "OBSERVED_OVERDUE" in alert_types:
        highlights["expected_completion_date"] = {
            "state": "strong_issue",
            "label": "Observed Overdue",
            "reason": "The work is observed overdue at the analytical snapshot date.",
        }
    if "PAYMENT_AUTH_BEFORE_REQUEST" in payment_codes:
        for field in ("payment_authorization_date", "payment_request_date"):
            highlights[field] = {
                "state": "review",
                "label": "Requires Review",
                "reason": "Authorization is recorded before the payment request.",
            }

    compliance_field_map = {
        "MPLADS-3.2.4-SANCTION-45D": "sanction_date_as_of",
        "MPLADS-3.2.17-PUBLIC-USE": "public_use_recorded_as_of",
        "MPLADS-11.3-ASSET-HANDOVER": "handover_recorded_as_of",
        "MPLADS-4.5.8-ASSET-REGISTER": "asset_record_count_as_of",
        "MPLADS-11.2-COMPLETION-UC": "uc_recorded_as_of",
    }
    for rule in compliance_rules:
        field = compliance_field_map.get(str(rule.get("rule_id")))
        result = str(rule.get("result") or "")
        if field and result in {"REVIEW", "NON_COMPLIANT"}:
            highlights[field] = {
                "state": "strong_issue" if result == "NON_COMPLIANT" else "review",
                "label": "Non-Compliant" if result == "NON_COMPLIANT" else "Requires Review",
                "reason": f"{rule.get('rule_title')}: {result.replace('_', ' ')}.",
            }

    def document_entry(
        key: str,
        label: str,
        profile_field: str | None,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        rule = compliance_by_id.get(rule_id or "")
        result = str((rule or {}).get("result") or "")
        source_value = profile.get(profile_field) if profile_field else None
        if result == "NON_COMPLIANT":
            status_code, status_label, state = "NON_COMPLIANT", "Non-Compliant", "strong_issue"
        elif result == "REVIEW":
            status_code, status_label, state = "REQUIRES_REVIEW", "Requires Review", "review"
        elif result == "PASS":
            status_code, status_label, state = "RECORDED", "Recorded / requirement satisfied", "pass"
        elif result == "INSUFFICIENT_DATA":
            status_code, status_label, state = "INSUFFICIENT_DATA", "Insufficient data", "insufficient"
        elif result == "NOT_APPLICABLE":
            if lifecycle in {"PRE_SANCTION", "EXECUTION"}:
                status_code, status_label, state = "EXPECTED_AFTER_COMPLETION", "Expected after completion", "not_applicable"
            else:
                status_code, status_label, state = "NOT_APPLICABLE", "Not applicable under current rule conditions", "not_applicable"
        elif _truth(source_value) or (source_value not in {None, "", 0, "0", False}):
            status_code, status_label, state = "RECORDED", "Recorded", "pass"
        elif lifecycle in {"PRE_SANCTION", "EXECUTION"}:
            status_code, status_label, state = "EXPECTED_AFTER_COMPLETION", "Expected after completion", "not_applicable"
        else:
            status_code, status_label, state = "NOT_RECORDED_AS_OF_SNAPSHOT", "Not recorded as of snapshot", "context"
        return {
            "key": key,
            "label": label,
            "status_code": status_code,
            "status_label": status_label,
            "state": state,
            "source_value": source_value,
            "rule_id": rule_id,
            "rule_result": result or None,
            "observed": (rule or {}).get("observed_value"),
        }

    readiness_entries: list[dict[str, Any]] = []
    if lifecycle == "PRE_SANCTION":
        readiness_entries += [
            document_entry("recommendation", "Recommendation record", "recommendation_date"),
            document_entry("sanction", "Sanction decision", "sanction_date_as_of", "MPLADS-3.2.4-SANCTION-45D"),
        ]
    elif lifecycle == "EXECUTION":
        readiness_entries += [
            document_entry("sanction", "Sanction record", "sanction_date_as_of", "MPLADS-3.2.4-SANCTION-45D"),
            document_entry("actual_start", "Actual start", "actual_start_date_as_of"),
            document_entry("latest_progress", "Latest progress report", "latest_progress_report_date_as_of"),
            document_entry("latest_payment", "Latest payment release", "last_payment_release_date_as_of"),
        ]
    else:
        readiness_entries += [
            document_entry("completion", "Completion record", "completion_date_as_of"),
            document_entry("final_expenditure", "Final expenditure", "final_expenditure_inr_as_of"),
        ]
    readiness_entries += [
        document_entry("utilization_certificate", "Utilization Certificate", "uc_recorded_as_of", DOCUMENT_RULES["utilization_certificate"]),
        document_entry("handover", "Handover", "handover_recorded_as_of", DOCUMENT_RULES["handover"]),
        document_entry("public_use", "Public use", "public_use_recorded_as_of", DOCUMENT_RULES["public_use"]),
        document_entry("completed_work_photograph", "Completed-work photograph", None, DOCUMENT_RULES["completed_work_photograph"]),
        document_entry("asset_register", "Asset register", "asset_record_count_as_of", DOCUMENT_RULES["asset_register"]),
        document_entry("audit", "Audit record", "audit_recorded_as_of"),
    ]

    timeline_events: list[dict[str, Any]] = []

    def event(label: str, field: str, kind: str, state: str = "recorded", detail_text: str | None = None, href: str | None = None) -> None:
        value = profile.get(field)
        if value not in {None, ""}:
            timeline_events.append({
                "label": label,
                "date": value,
                "kind": kind,
                "state": state,
                "detail": detail_text,
                "href": href,
                "source_field": field,
            })

    event("Recommendation", "recommendation_date", "observed")
    sanction_rule = compliance_by_id.get("MPLADS-3.2.4-SANCTION-45D")
    sanction_state = "review" if sanction_rule and sanction_rule.get("result") == "REVIEW" else "recorded"
    event(
        "Sanction",
        "sanction_date_as_of",
        "observed",
        sanction_state,
        "The recorded recommendation-to-sanction interval requires verification." if sanction_state == "review" else None,
        "#compliance",
    )
    event("Expected start", "expected_start_date", "planned", "planned")
    event("Actual start", "actual_start_date_as_of", "observed")
    if authorization_date:
        timeline_events.append({
            "label": "Payment authorization",
            "date": authorization_date,
            "kind": "observed",
            "state": "review",
            "detail": "Authorization is recorded before the request.",
            "href": "#payments",
            "source_field": "payment_authorization_date",
        })
    if request_date:
        timeline_events.append({
            "label": "Payment request",
            "date": request_date,
            "kind": "observed",
            "state": "review",
            "detail": "The request is recorded after authorization.",
            "href": "#payments",
            "source_field": "payment_request_date",
        })
    event("First payment release", "first_payment_release_date_as_of", "observed")
    event(
        "Last payment release",
        "last_payment_release_date_as_of",
        "observed",
        exceedance_severity["state"] if observed_over_sanction else "recorded",
        "Released payments exceed the visible sanctioned amount." if observed_over_sanction else None,
        "#payments",
    )
    event("First progress report", "first_progress_report_date_as_of", "observed")
    event(
        "Latest progress report",
        "latest_progress_report_date_as_of",
        "observed",
        "review" if "FUND_PROGRESS_REVIEW" in alert_types else "recorded",
        "Financial progress is materially different from physical progress and requires reconciliation."
        if "FUND_PROGRESS_REVIEW" in alert_types else None,
        "#payments",
    )
    event(
        "Expected completion",
        "expected_completion_date",
        "planned",
        "strong_issue" if "OBSERVED_OVERDUE" in alert_types else "planned",
        "The expected completion date has passed at the analytical snapshot date."
        if "OBSERVED_OVERDUE" in alert_types else "The expected completion date has not yet been reached at the analytical snapshot."
        if str(profile.get("expected_completion_date") or "") > str(profile.get("feature_snapshot_date") or "") else None,
        "#forecast",
    )
    event("Recorded completion", "completion_date_as_of", "observed")
    timeline_events.sort(key=lambda item: (str(item["date"]), item["label"]))
    timeline_attention = [item for item in timeline_events if item["state"] in {"review", "strong_issue"}]

    compliance_counts = {key: 0 for key in ("PASS", "REVIEW", "NON_COMPLIANT", "NOT_APPLICABLE", "INSUFFICIENT_DATA")}
    for rule in compliance_rules:
        result = str(rule.get("result") or "")
        if result in compliance_counts:
            compliance_counts[result] += 1

    checklist: list[str] = []
    if observed_over_sanction:
        checklist += ["Check the original sanction order", "Check any approved revised sanction or authorized cost variation"]
    if "FUND_PROGRESS_REVIEW" in alert_types:
        checklist += ["Reconcile payment/PFMS records", "Verify the latest physical progress and supporting reports"]
    if "PAYMENT_AUTH_BEFORE_REQUEST" in payment_codes:
        checklist.append("Verify payment request and authorization chronology")
    if any(rule.get("result") in {"REVIEW", "NON_COMPLIANT"} for rule in compliance_rules):
        checklist.append("Verify documents required by the cited MPLADS rules")
    if (detail.get("duplicates") or {}).get("review_candidates"):
        checklist.append("Compare the paired duplicate-review work")
    if "OBSERVED_OVERDUE" in alert_types:
        checklist.append("Verify any approved extension or revised schedule")
    checklist = list(dict.fromkeys(checklist)) or ["Confirm the work record against authoritative source documents"]

    actionable_signals = [item for item in warning_signals if is_actionable_alert(item["technical_reference"]["alert_type"])]
    main_attention = [item["title"] for item in actionable_signals[:4]]
    if not main_attention:
        main_attention = ["No major current actionable review condition is present."]

    actionable_rules = [rule for rule in compliance_rules if rule.get("result") in {"REVIEW", "NON_COMPLIANT"}]
    case_assessment = {
        "title": "AI-Assisted Case Assessment",
        "project": {
            "work_id": profile.get("work_id"),
            "work_title": profile.get("work_description"),
            "location": ", ".join(str(value) for value in (profile.get("village"), profile.get("block"), profile.get("district"), profile.get("state_name")) if value),
            "lifecycle": lifecycle,
            "review_priority_score": (detail.get("priority") or {}).get("review_priority_score_0_100"),
            "review_priority_band": (detail.get("priority") or {}).get("review_priority_band"),
            "attention_level": attention_level,
        },
        "executive_summary": (
            f"This {lifecycle.replace('_', ' ').lower()}-stage work has {ATTENTION_LEVEL_LABELS[attention_level].lower()} "
            f"under the frozen Review Priority and current actionable evidence."
        ),
        "main_observations": actionable_signals,
        "financial_and_payment": {
            "sanctioned_amount_inr": sanction,
            "released_payments_inr": released,
            "difference_inr": difference,
            "percentage_above_sanction": above_pct,
            "display_severity": exceedance_severity,
            "authorization_date": authorization_date,
            "request_date": request_date,
        },
        "progress_and_schedule": {
            "physical_progress_pct": physical,
            "financial_progress_pct": financial,
            "gap_percentage_points": gap,
            "persistent_gap": persistent_gap,
            "expected_completion_date": profile.get("expected_completion_date"),
            "completion_date": profile.get("completion_date_as_of"),
            "snapshot_date": profile.get("feature_snapshot_date"),
            "overdue_days": profile.get("overdue_days_as_of"),
        },
        "compliance_checks": [{
            "title": rule.get("rule_title"),
            "status": "Non-Compliant" if rule.get("result") == "NON_COMPLIANT" else "Requires Review",
            "observed": rule.get("observed_value"),
            "expected": rule.get("expected_condition"),
            "clause": rule.get("guideline_clause"),
            "page": rule.get("guideline_page"),
            "rule_id": rule.get("rule_id"),
            "chunk_ids": rule.get("guideline_chunk_ids"),
        } for rule in actionable_rules],
        "duplicate_review": (detail.get("duplicates") or {}).get("review_candidates") or [],
        "peer_comparisons": peer_comparisons,
        "operational_context": trend_presentation,
        "verification_steps": checklist,
        "review_note": REVIEW_NOTE,
    }

    return {
        "family_labels": FAMILY_LABELS,
        "attention_level": attention_level,
        "attention_level_label": ATTENTION_LEVEL_LABELS[attention_level],
        "requires_review": requires_review,
        "main_attention_areas": main_attention,
        "highlighted_fields": highlights,
        "warning_signals": warning_signals,
        "financial": {
            "sanctioned_amount_inr": sanction,
            "released_payments_inr": released,
            "released_minus_sanction_inr": difference,
            "percentage_above_sanction": above_pct,
            "physical_progress_pct": physical,
            "financial_progress_pct": financial,
            "financial_minus_physical_gap_percentage_points": gap,
            "released_exceeds_visible_sanction": observed_over_sanction,
            "persistent_gap": persistent_gap,
            "exceedance_display_severity": exceedance_severity,
        },
        "payment_chronology": {
            "authorization_before_request": "PAYMENT_AUTH_BEFORE_REQUEST" in payment_codes,
            "authorization_date": authorization_date,
            "request_date": request_date,
        },
        "document_readiness": {
            "lifecycle": lifecycle,
            "headline": (
                "Completion records are expected later; this work is currently in execution."
                if lifecycle == "EXECUTION"
                else "Execution and completion records are expected at later lifecycle stages."
                if lifecycle == "PRE_SANCTION"
                else "Completion and closure records are evaluated against their exact deterministic rule status."
            ),
            "entries": readiness_entries,
        },
        "peer_comparisons": peer_comparisons,
        "trend": trend_presentation,
        "case_assessment": case_assessment,
        "compliance_counts": compliance_counts,
        "timeline": {
            "attention_count": len(timeline_attention),
            "attention_labels": [item["label"] for item in timeline_attention],
            "events": timeline_events,
        },
        "officer_verification_checklist": checklist,
        "review_note": REVIEW_NOTE,
        "as_of_date": profile.get("feature_snapshot_date", date.today().isoformat()),
    }
