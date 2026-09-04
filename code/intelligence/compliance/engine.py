"""Lifecycle-aware deterministic compliance evaluation and work summaries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd

from .models import ComplianceResult, ComplianceRule, RuleContext, RuleOutcome
from .rules import IMPLEMENTED_RULES


EVIDENCE_COLUMNS = (
    "work_id",
    "rule_id",
    "rule_title",
    "rule_category",
    "lifecycle_stage",
    "result",
    "severity",
    "observed_value",
    "expected_condition",
    "evidence",
    "guideline_version",
    "guideline_chapter",
    "guideline_clause",
    "guideline_page",
    "guideline_printed_page",
    "guideline_chunk_ids",
    "official_reference",
    "as_of_date",
)

SUMMARY_COLUMNS = (
    "work_id",
    "rules_evaluated_count",
    "rules_passed_count",
    "rules_review_count",
    "rules_non_compliant_count",
    "rules_insufficient_data_count",
    "rules_not_applicable_count",
    "highest_compliance_evidence_severity",
    "top_compliance_rule_id",
)

_SEVERITY_PRIORITY = {"INFO": 1, "WARNING": 2, "STRONG_WARNING": 3}
_RESULT_PRIORITY = {
    "PASS": 0,
    "NOT_APPLICABLE": 0,
    "INSUFFICIENT_DATA": 1,
    "REVIEW": 2,
    "NON_COMPLIANT": 3,
}


def _validate_inputs(
    features: pd.DataFrame,
    assets: pd.DataFrame,
    rules: Iterable[ComplianceRule],
) -> None:
    problems: list[str] = []
    if "work_id" not in features or "lifecycle_stage" not in features:
        problems.append("features require work_id and lifecycle_stage")
    if features.get("work_id", pd.Series(dtype="object")).duplicated().any():
        problems.append("feature work_id values must be unique")
    if "work_id" not in assets:
        problems.append("assets require work_id")
    for rule in rules:
        for reference in rule.spec.required_fields:
            table, field = reference.split(".", maxsplit=1)
            columns = features.columns if table == "features" else assets.columns
            if field not in columns:
                problems.append(f"{rule.spec.rule_id} missing {reference}")
    if problems:
        raise ValueError("; ".join(problems))


def _not_applicable(lifecycle: str, rule: ComplianceRule) -> RuleOutcome:
    return RuleOutcome(
        result=ComplianceResult.NOT_APPLICABLE,
        observed_value=f"lifecycle_stage={lifecycle}",
        expected_condition=(
            "Applicable lifecycle stages: " + ", ".join(rule.spec.lifecycle_stages)
        ),
        evidence="The rule is outside this work's current as-of lifecycle.",
    )


def build_compliance_evidence(
    features: pd.DataFrame,
    assets: pd.DataFrame,
    as_of_date: date,
    rules: Iterable[ComplianceRule] = IMPLEMENTED_RULES,
) -> pd.DataFrame:
    """Evaluate every rule once per work while preserving lifecycle applicability."""

    selected_rules = tuple(rules)
    _validate_inputs(features, assets, selected_rules)
    asset_groups = {
        str(work_id): tuple(group.to_dict(orient="records"))
        for work_id, group in assets.groupby("work_id", sort=False)
    }
    records: list[dict[str, object]] = []
    for work in features.to_dict(orient="records"):
        work_id = str(work["work_id"])
        lifecycle = str(work["lifecycle_stage"])
        context = RuleContext(
            work=work,
            asset_records=asset_groups.get(work_id, ()),
            as_of_date=as_of_date,
        )
        for rule in selected_rules:
            outcome = (
                rule.evaluate(context)
                if lifecycle in rule.spec.lifecycle_stages
                else _not_applicable(lifecycle, rule)
            )
            spec = rule.spec
            records.append(
                {
                    "work_id": work_id,
                    "rule_id": spec.rule_id,
                    "rule_title": spec.title,
                    "rule_category": spec.category,
                    "lifecycle_stage": lifecycle,
                    "result": outcome.result.value,
                    "severity": spec.severity.value,
                    "observed_value": outcome.observed_value,
                    "expected_condition": outcome.expected_condition,
                    "evidence": outcome.evidence,
                    "guideline_version": spec.guideline_version,
                    "guideline_chapter": spec.guideline_chapter,
                    "guideline_clause": spec.guideline_clause,
                    "guideline_page": spec.guideline_page,
                    "guideline_printed_page": spec.guideline_printed_page,
                    "guideline_chunk_ids": ";".join(spec.guideline_chunk_ids),
                    "official_reference": spec.official_reference,
                    "as_of_date": as_of_date.isoformat(),
                }
            )
    evidence = pd.DataFrame.from_records(records, columns=EVIDENCE_COLUMNS)
    allowed = {item.value for item in ComplianceResult}
    observed = set(evidence["result"].unique())
    if not observed.issubset(allowed):
        raise RuntimeError(f"Unsupported compliance results: {sorted(observed - allowed)}")
    expected_rows = len(features) * len(selected_rules)
    if len(evidence) != expected_rows:
        raise RuntimeError(
            f"Expected {expected_rows} work-rule rows, found {len(evidence)}"
        )
    return evidence


def build_compliance_summary(
    features: pd.DataFrame,
    evidence: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate rule outcomes to exactly one transparent row per work."""

    status_columns = {
        "PASS": "rules_passed_count",
        "REVIEW": "rules_review_count",
        "NON_COMPLIANT": "rules_non_compliant_count",
        "INSUFFICIENT_DATA": "rules_insufficient_data_count",
        "NOT_APPLICABLE": "rules_not_applicable_count",
    }
    counts = (
        evidence.groupby(["work_id", "result"]).size().unstack(fill_value=0)
    )
    summary = pd.DataFrame({"work_id": features["work_id"].astype(str)})
    for result, column in status_columns.items():
        values = counts[result] if result in counts else pd.Series(dtype="int64")
        summary[column] = summary["work_id"].map(values).fillna(0).astype("int64")
    summary["rules_evaluated_count"] = (
        summary["rules_passed_count"]
        + summary["rules_review_count"]
        + summary["rules_non_compliant_count"]
        + summary["rules_insufficient_data_count"]
    )

    actionable = evidence.loc[
        evidence["result"].isin(["REVIEW", "NON_COMPLIANT", "INSUFFICIENT_DATA"])
    ].copy()
    actionable["_result_priority"] = actionable["result"].map(_RESULT_PRIORITY)
    actionable["_severity_priority"] = actionable["severity"].map(_SEVERITY_PRIORITY)
    actionable = actionable.sort_values(
        ["work_id", "_result_priority", "_severity_priority", "rule_id"],
        ascending=[True, False, False, True],
        kind="stable",
    )
    top = actionable.drop_duplicates("work_id", keep="first").set_index("work_id")
    summary["highest_compliance_evidence_severity"] = (
        summary["work_id"].map(top["severity"]).fillna("NONE")
    )
    summary["top_compliance_rule_id"] = summary["work_id"].map(top["rule_id"])

    summary = summary[
        [
            "work_id",
            "rules_evaluated_count",
            "rules_passed_count",
            "rules_review_count",
            "rules_non_compliant_count",
            "rules_insufficient_data_count",
            "rules_not_applicable_count",
            "highest_compliance_evidence_severity",
            "top_compliance_rule_id",
        ]
    ]
    if len(summary) != 3_000 or not summary["work_id"].is_unique:
        raise RuntimeError("Compliance summary must contain 3,000 unique work IDs")
    represented = summary[list(status_columns.values())].sum(axis=1)
    expected_per_work = evidence["rule_id"].nunique()
    if not represented.eq(expected_per_work).all():
        raise RuntimeError("Compliance summary status counts do not cover every rule")
    return summary
