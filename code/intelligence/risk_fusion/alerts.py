"""Problem-specific Day-7 alerts that preserve their detector provenance."""

from __future__ import annotations

import pandas as pd

from .policy import (
    ANOMALY,
    COMPLIANCE,
    COST_OVERRUN_PREDICTION,
    DUPLICATE_REVIEW,
    OBSERVED_CONDITIONS,
    OPERATIONAL_TREND_CONTEXT,
    PAYMENT_EXECUTION,
    PEER_DEVIATION,
)
from .signals import as_bool


ALERT_COLUMNS = [
    "alert_id",
    "work_id",
    "lifecycle_stage",
    "alert_type",
    "evidence_code",
    "alert_strength_0_100",
    "alert_summary",
    "source_artifact",
    "source_record_reference",
]


def _signal_lookup(signals: dict[str, pd.DataFrame], family: str) -> pd.DataFrame:
    return signals[family].set_index("work_id")


def build_review_alerts(
    features: pd.DataFrame,
    anomaly: pd.DataFrame,
    peer: pd.DataFrame,
    duplicates: pd.DataFrame,
    payment_evidence: pd.DataFrame,
    fund_progress: pd.DataFrame,
    compliance_evidence: pd.DataFrame,
    predictive: pd.DataFrame,
    trend_context: pd.DataFrame,
    signals: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    lifecycle = features.set_index("work_id")["lifecycle_stage"]
    records: list[dict[str, object]] = []

    def add(
        work_id: str,
        alert_type: str,
        evidence_code: str,
        strength: float,
        summary: str,
        source: str,
        reference: str | None = None,
    ) -> None:
        records.append(
            {
                "work_id": work_id,
                "lifecycle_stage": lifecycle.loc[work_id],
                "alert_type": alert_type,
                "evidence_code": evidence_code,
                "alert_strength_0_100": float(max(0.0, min(100.0, strength))),
                "alert_summary": summary,
                "source_artifact": source,
                "source_record_reference": reference or f"work_id={work_id}",
            }
        )

    anomaly_signal = _signal_lookup(signals, ANOMALY)
    for row in anomaly.loc[
        pd.to_numeric(anomaly["within_stage_anomaly_percentile_0_100"], errors="coerce").ge(90)
    ].itertuples(index=False):
        add(
            row.work_id,
            "STATISTICAL_ANOMALY",
            "LIFECYCLE_ANOMALY_TOP_DECILE",
            float(row.within_stage_anomaly_percentile_0_100),
            anomaly_signal.loc[row.work_id, "evidence_summary"],
            "data/processed/anomaly_scores.csv",
        )

    peer_signal = _signal_lookup(signals, PEER_DEVIATION)
    for row in peer.loc[pd.to_numeric(peer["peer_outlier_count"], errors="coerce").fillna(0).gt(0)].itertuples(index=False):
        add(
            row.work_id,
            "PEER_DEVIATION",
            "STATISTICAL_PEER_OUTLIER",
            float(peer_signal.loc[row.work_id, "family_score_0_100"]),
            peer_signal.loc[row.work_id, "evidence_summary"],
            "data/processed/peer_benchmark_summary.csv",
        )

    duplicate_signal = _signal_lookup(signals, DUPLICATE_REVIEW)
    for row in duplicates.loc[as_bool(duplicates["review_candidate"])].itertuples(index=False):
        add(
            row.work_id,
            "DUPLICATE_REVIEW_CANDIDATE",
            "DAY4_1_CORROBORATED_REVIEW_CANDIDATE",
            float(duplicate_signal.loc[row.work_id, "family_score_0_100"]),
            duplicate_signal.loc[row.work_id, "evidence_summary"],
            "data/processed/duplicate_summary.csv",
        )

    payment_signal = _signal_lookup(signals, PAYMENT_EXECUTION)
    usable_payment = payment_evidence.loc[
        ~payment_evidence["signal_code"].eq("RELEASED_TOTAL_EXCEEDS_SANCTION")
    ]
    for work_id, group in usable_payment.groupby("work_id", sort=True):
        codes = ";".join(sorted(group["signal_code"].unique()))
        add(
            work_id,
            "PAYMENT_IRREGULARITY",
            codes,
            float(payment_signal.loc[work_id, "family_score_0_100"]),
            f"Payment review evidence codes: {codes}. Over-sanction evidence is assigned separately.",
            "data/processed/payment_irregularities.csv",
        )

    gap_mask = as_bool(fund_progress["current_large_positive_fund_gap_review_heuristic"]) | as_bool(
        fund_progress["persistent_large_reported_gap_review_heuristic"]
    )
    for row in fund_progress.loc[gap_mask].itertuples(index=False):
        add(
            row.work_id,
            "FUND_PROGRESS_REVIEW",
            (
                "PERSISTENT_FUND_PROGRESS_REVIEW"
                if bool(row.persistent_large_reported_gap_review_heuristic)
                else "CURRENT_LARGE_POSITIVE_FUND_GAP"
            ),
            float(payment_signal.loc[row.work_id, "family_score_0_100"]),
            (
                f"Current fund-minus-physical gap {row.fund_minus_physical_gap_pct_as_of:.3f} points; "
                f"persistent large-gap evidence={bool(row.persistent_large_reported_gap_review_heuristic)}."
            ),
            "data/processed/fund_progress_evidence.csv",
        )

    observed_signal = _signal_lookup(signals, OBSERVED_CONDITIONS)
    for row in predictive.loc[as_bool(predictive["already_overdue_as_of"])].itertuples(index=False):
        add(
            row.work_id,
            "OBSERVED_OVERDUE",
            "OBSERVED_OVERDUE_AS_OF",
            float(observed_signal.loc[row.work_id, "family_score_0_100"]),
            "Work is factually overdue at the controlled snapshot; this is not a model prediction.",
            "data/processed/predictive_scores.csv",
        )
    for row in predictive.loc[as_bool(predictive["already_over_sanction_as_of"])].itertuples(index=False):
        add(
            row.work_id,
            "OBSERVED_OVER_SANCTION",
            "OBSERVED_OVER_SANCTION_AS_OF",
            float(observed_signal.loc[row.work_id, "family_score_0_100"]),
            "Visible released total already exceeds sanctioned amount; counted only in observed conditions.",
            "data/processed/predictive_scores.csv",
        )

    compliance_signal = _signal_lookup(signals, COMPLIANCE)
    reviews = compliance_evidence.loc[compliance_evidence["result"].eq("REVIEW")]
    for work_id, group in reviews.groupby("work_id", sort=True):
        strongest = group.assign(
            _severity=group["severity"].map({"INFO": 1, "WARNING": 2, "STRONG_WARNING": 3})
        ).sort_values(["_severity", "rule_id"], ascending=[False, True], kind="stable").iloc[0]
        add(
            work_id,
            "COMPLIANCE_REVIEW",
            str(strongest["rule_id"]),
            float(compliance_signal.loc[work_id, "family_score_0_100"]),
            f"Actionable compliance REVIEW under {strongest['rule_id']} ({strongest['severity']}).",
            "data/processed/compliance_evidence.csv",
            f"work_id={work_id};rule_id={strongest['rule_id']}",
        )
    non_compliant = compliance_evidence.loc[compliance_evidence["result"].eq("NON_COMPLIANT")]
    for row in non_compliant.itertuples(index=False):
        add(
            row.work_id,
            "DETERMINISTIC_NON_COMPLIANCE",
            row.rule_id,
            100.0,
            f"Deterministic NON_COMPLIANT result under {row.rule_id}; human review remains required.",
            "data/processed/compliance_evidence.csv",
            f"work_id={row.work_id};rule_id={row.rule_id}",
        )

    cost_signal = _signal_lookup(signals, COST_OVERRUN_PREDICTION)
    cost_percentile = pd.to_numeric(
        predictive["cost_overrun_serving_percentile_0_100"], errors="coerce"
    )
    cost_mask = cost_percentile.ge(90.0) & ~as_bool(predictive["already_over_sanction_as_of"])
    for row in predictive.loc[cost_mask].itertuples(index=False):
        add(
            row.work_id,
            "COST_OVERRUN_EARLY_WARNING",
            "RAW_XGBOOST_SECONDARY_TOP_DECILE",
            float(cost_signal.loc[row.work_id, "family_score_0_100"]),
            "Top-decile weak raw-XGBoost early-warning evidence; not a calibrated probability or observed overrun.",
            "data/processed/predictive_scores.csv",
        )

    trend_signal = _signal_lookup(signals, OPERATIONAL_TREND_CONTEXT)
    for row in trend_context.loc[as_bool(trend_context["operational_trend_deviation_flag"])].itertuples(index=False):
        add(
            row.work_id,
            "OPERATIONAL_TREND_DEVIATION",
            "SUPPORTED_LATEST_MONTH_OPERATIONAL_TREND",
            float(trend_signal.loc[row.work_id, "family_score_0_100"]),
            trend_signal.loc[row.work_id, "evidence_summary"],
            "data/processed/work_trend_context.csv",
        )

    alerts = pd.DataFrame.from_records(records)
    alerts = alerts.sort_values(
        ["alert_type", "work_id", "evidence_code"], kind="stable"
    ).reset_index(drop=True)
    alerts.insert(
        0,
        "alert_id",
        [f"D7-{index:06d}" for index in range(1, len(alerts) + 1)],
    )
    return alerts[ALERT_COLUMNS]
