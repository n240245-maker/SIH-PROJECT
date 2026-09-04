"""Normalize frozen detector evidence into independent 0-100 family signals."""

from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence.trends.robust import percentile_0_100

from .policy import (
    ANOMALY,
    COMPLIANCE,
    COST_OVERRUN_PREDICTION,
    DUPLICATE_REVIEW,
    OBSERVED_CONDITIONS,
    OPERATIONAL_TREND_CONTEXT,
    PAYMENT_EXECUTION,
    PEER_DEVIATION,
    SOURCE_ARTIFACTS,
)


SIGNAL_COLUMNS = [
    "work_id",
    "family",
    "family_score_0_100",
    "source_artifact",
    "evidence_code",
    "evidence_summary",
    "data_available",
]

PAYMENT_SEVERITY_SCORE = {"INFO": 25.0, "WARNING": 60.0, "STRONG_WARNING": 90.0}
COMPLIANCE_REVIEW_SCORE = {"INFO": 30.0, "WARNING": 60.0, "STRONG_WARNING": 80.0}


def as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.casefold().eq("true").fillna(False)


def _finalize(frame: pd.DataFrame, family: str) -> pd.DataFrame:
    result = frame.copy()
    result.insert(1, "family", family)
    result["family_score_0_100"] = pd.to_numeric(
        result["family_score_0_100"], errors="coerce"
    ).fillna(0.0).clip(0.0, 100.0)
    result["source_artifact"] = SOURCE_ARTIFACTS[family]
    result["data_available"] = as_bool(result["data_available"])
    return result[SIGNAL_COLUMNS]


def anomaly_signal(spine: pd.DataFrame, anomaly: pd.DataFrame) -> pd.DataFrame:
    result = spine[["work_id"]].merge(
        anomaly[["work_id", "within_stage_anomaly_percentile_0_100"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    score = pd.to_numeric(result["within_stage_anomaly_percentile_0_100"], errors="coerce")
    result["family_score_0_100"] = score
    result["evidence_code"] = "LIFECYCLE_ANOMALY_PERCENTILE"
    result["evidence_summary"] = score.map(
        lambda value: (
            f"Within-lifecycle statistical unusualness percentile {value:.3f}; not a probability."
            if pd.notna(value)
            else "Lifecycle anomaly score unavailable."
        )
    )
    result["data_available"] = score.notna()
    return _finalize(result, ANOMALY)


def peer_signal(spine: pd.DataFrame, peer: pd.DataFrame) -> pd.DataFrame:
    result = spine[["work_id", "lifecycle_stage"]].merge(
        peer[["work_id", "peer_outlier_count", "max_abs_peer_deviation", "top_peer_deviation_metric"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    count = pd.to_numeric(result["peer_outlier_count"], errors="coerce")
    deviation = pd.to_numeric(result["max_abs_peer_deviation"], errors="coerce")
    outlier = count.fillna(0).gt(0) & deviation.notna()
    score = pd.Series(0.0, index=result.index)
    for _, index in result.loc[outlier].groupby("lifecycle_stage").groups.items():
        score.loc[index] = percentile_0_100(deviation.loc[index])
    result["family_score_0_100"] = score
    result["evidence_code"] = np.where(
        outlier, "STATISTICAL_PEER_OUTLIER", "NO_STATISTICAL_PEER_OUTLIER"
    )
    result["evidence_summary"] = [
        (
            f"{int(c)} peer-outlier metric(s); strongest {m} has absolute robust deviation {d:.3f}."
            if flag
            else "No metric met the statistical peer-outlier evidence heuristic."
        )
        for c, m, d, flag in zip(
            count.fillna(0), result["top_peer_deviation_metric"], deviation, outlier
        )
    ]
    result["data_available"] = count.notna()
    return _finalize(result, PEER_DEVIATION)


def duplicate_signal(spine: pd.DataFrame, duplicates: pd.DataFrame) -> pd.DataFrame:
    result = spine[["work_id"]].merge(
        duplicates[["work_id", "review_candidate", "best_review_similarity_score_0_100"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    review = as_bool(result["review_candidate"])
    similarity = pd.to_numeric(result["best_review_similarity_score_0_100"], errors="coerce")
    result["family_score_0_100"] = similarity.where(review, 0.0)
    result["evidence_code"] = np.where(
        review, "DUPLICATE_REVIEW_CANDIDATE", "NO_DUPLICATE_REVIEW_CANDIDATE"
    )
    result["evidence_summary"] = [
        (
            f"Corroborated Day-4.1 duplicate review candidate; best similarity score {score:.3f}."
            if flag
            else "No corroborated Day-4.1 duplicate review candidate."
        )
        for flag, score in zip(review, similarity.fillna(0.0))
    ]
    result["data_available"] = result["review_candidate"].notna()
    return _finalize(result, DUPLICATE_REVIEW)


def payment_execution_signal(
    spine: pd.DataFrame,
    payment_summary: pd.DataFrame,
    payment_evidence: pd.DataFrame,
    fund_progress: pd.DataFrame,
) -> pd.DataFrame:
    result = spine[["work_id"]].merge(
        payment_summary[["work_id"]], on="work_id", how="left", validate="one_to_one", indicator="_payment_merge"
    )
    usable = payment_evidence.loc[
        ~payment_evidence["signal_code"].eq("RELEASED_TOTAL_EXCEEDS_SANCTION")
    ].copy()
    usable["_score"] = usable["signal_severity"].map(PAYMENT_SEVERITY_SCORE)
    strongest_payment = (
        usable.sort_values(["work_id", "_score", "signal_code"], ascending=[True, False, True], kind="stable")
        .drop_duplicates("work_id", keep="first")
        .set_index("work_id")
    )
    result["_payment_score"] = result["work_id"].map(strongest_payment["_score"]).fillna(0.0)
    result["_payment_code"] = result["work_id"].map(strongest_payment["signal_code"])

    fund_columns = [
        "work_id",
        "fund_minus_physical_gap_pct_as_of",
        "persistent_large_reported_gap_review_heuristic",
    ]
    result = result.merge(
        fund_progress[fund_columns], on="work_id", how="left", validate="one_to_one", indicator="_fund_merge"
    )
    gap = pd.to_numeric(result["fund_minus_physical_gap_pct_as_of"], errors="coerce")
    positive = gap.gt(0)
    gap_percentile = pd.Series(0.0, index=result.index)
    gap_percentile.loc[positive] = percentile_0_100(gap.loc[positive])
    persistence = as_bool(result["persistent_large_reported_gap_review_heuristic"])
    result["_gap_score"] = (gap_percentile + persistence.astype(float) * 10.0).clip(upper=100.0)
    result["family_score_0_100"] = result[["_payment_score", "_gap_score"]].max(axis=1)
    payment_drives = result["_payment_score"].gt(result["_gap_score"])
    result["evidence_code"] = np.where(
        payment_drives,
        result["_payment_code"].fillna("PAYMENT_IRREGULARITY"),
        np.where(
            result["_gap_score"].gt(0),
            "FUND_PROGRESS_REVIEW",
            "NO_PAYMENT_EXECUTION_SIGNAL",
        ),
    )
    result.loc[result["_gap_score"].gt(0) & persistence, "evidence_code"] = "PERSISTENT_FUND_PROGRESS_REVIEW"
    result["evidence_summary"] = [
        (
            f"Capped payment/execution family: payment severity score {p:.1f}; "
            f"positive fund-progress score {g:.3f}; persistence boost {'10' if keep else '0'} points."
        )
        for p, g, keep in zip(result["_payment_score"], result["_gap_score"], persistence)
    ]
    result["data_available"] = result["_payment_merge"].eq("both") & result["_fund_merge"].eq("both")
    return _finalize(result, PAYMENT_EXECUTION)


def observed_conditions_signal(
    spine: pd.DataFrame,
    features: pd.DataFrame,
    predictive: pd.DataFrame,
) -> pd.DataFrame:
    result = spine[["work_id", "lifecycle_stage"]].merge(
        features[["work_id", "overdue_days_as_of", "financial_overrun_pct_as_of"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    ).merge(
        predictive[["work_id", "already_overdue_as_of", "already_over_sanction_as_of"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    execution = result["lifecycle_stage"].eq("EXECUTION")
    overdue = execution & as_bool(result["already_overdue_as_of"])
    over_sanction = execution & as_bool(result["already_over_sanction_as_of"])
    overdue_days = pd.to_numeric(result["overdue_days_as_of"], errors="coerce")
    overrun_pct = pd.to_numeric(result["financial_overrun_pct_as_of"], errors="coerce")
    overdue_score = pd.Series(0.0, index=result.index)
    over_sanction_score = pd.Series(0.0, index=result.index)
    overdue_score.loc[overdue] = 50.0 + 0.5 * percentile_0_100(overdue_days.loc[overdue])
    over_sanction_score.loc[over_sanction] = 75.0 + 0.25 * percentile_0_100(
        overrun_pct.loc[over_sanction]
    )
    result["family_score_0_100"] = pd.concat(
        [overdue_score, over_sanction_score], axis=1
    ).max(axis=1)
    result["evidence_code"] = np.select(
        [overdue & over_sanction, over_sanction, overdue],
        ["OBSERVED_OVERDUE_AND_OVER_SANCTION", "OBSERVED_OVER_SANCTION", "OBSERVED_OVERDUE"],
        default="NO_OBSERVED_CONDITION",
    )
    result["evidence_summary"] = [
        (
            f"Observed overdue={is_overdue} (days={days if pd.notna(days) else 'n/a'}, score={ods:.3f}); "
            f"observed over sanction={is_over} (overrun_pct={pct if pd.notna(pct) else 'n/a'}, score={oss:.3f})."
        )
        for is_overdue, days, ods, is_over, pct, oss in zip(
            overdue, overdue_days, overdue_score, over_sanction, overrun_pct, over_sanction_score
        )
    ]
    result["data_available"] = execution & result["already_overdue_as_of"].notna() & result["already_over_sanction_as_of"].notna()
    return _finalize(result, OBSERVED_CONDITIONS)


def compliance_signal(spine: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    actionable = evidence.loc[evidence["result"].isin(["REVIEW", "NON_COMPLIANT"])].copy()
    actionable["_score"] = np.where(
        actionable["result"].eq("NON_COMPLIANT"),
        100.0,
        actionable["severity"].map(COMPLIANCE_REVIEW_SCORE).fillna(0.0),
    )
    strongest = (
        actionable.sort_values(
            ["work_id", "_score", "rule_id"], ascending=[True, False, True], kind="stable"
        )
        .drop_duplicates("work_id", keep="first")
        .set_index("work_id")
    )
    counts = evidence.groupby("work_id").size()
    result = spine[["work_id"]].copy()
    result["family_score_0_100"] = result["work_id"].map(strongest["_score"]).fillna(0.0)
    result["evidence_code"] = result["work_id"].map(strongest["rule_id"]).fillna("NO_ACTIONABLE_COMPLIANCE_RESULT")
    top_result = result["work_id"].map(strongest["result"])
    top_severity = result["work_id"].map(strongest["severity"])
    result["evidence_summary"] = [
        (
            f"Strongest actionable compliance result {status}/{severity} under rule {code}."
            if pd.notna(status)
            else "No REVIEW or deterministic NON_COMPLIANT compliance result."
        )
        for status, severity, code in zip(top_result, top_severity, result["evidence_code"])
    ]
    result["data_available"] = result["work_id"].map(counts).fillna(0).gt(0)
    return _finalize(result, COMPLIANCE)


def cost_prediction_signal(spine: pd.DataFrame, predictive: pd.DataFrame) -> pd.DataFrame:
    required = {
        "work_id",
        "lifecycle_stage",
        "cost_overrun_calibration_status",
        "cost_overrun_calibration_serving_eligible",
        "cost_overrun_model_quality_status",
        "cost_overrun_serving_percentile_0_100",
    }
    missing = required.difference(predictive.columns)
    if missing:
        raise ValueError(f"Predictive scores lack governed serving fields: {sorted(missing)}")
    execution = predictive["lifecycle_stage"].eq("EXECUTION")
    if not predictive.loc[execution, "cost_overrun_calibration_status"].eq("UNSTABLE_RANK_REVERSAL").all():
        raise ValueError("Unexpected calibration status; fusion stopped")
    if as_bool(predictive.loc[execution, "cost_overrun_calibration_serving_eligible"]).any():
        raise ValueError("Calibration is incorrectly marked serving eligible; fusion stopped")
    if not predictive.loc[execution, "cost_overrun_model_quality_status"].eq("PROTOTYPE_WEAK_DISCRIMINATION").all():
        raise ValueError("Unexpected cost-overrun model-quality status; fusion stopped")

    result = spine[["work_id", "lifecycle_stage"]].merge(
        predictive[["work_id", "cost_overrun_serving_percentile_0_100"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    execution = result["lifecycle_stage"].eq("EXECUTION")
    serving = pd.to_numeric(result["cost_overrun_serving_percentile_0_100"], errors="coerce")
    if serving.loc[execution].isna().any() or not serving.loc[execution].between(0, 100).all():
        raise ValueError("Execution serving percentiles are missing or out of range")
    result["family_score_0_100"] = serving.where(execution, 0.0)
    result["evidence_code"] = np.where(
        execution, "RAW_XGBOOST_SECONDARY_EARLY_WARNING", "NOT_APPLICABLE_STAGE"
    )
    result["evidence_summary"] = [
        (
            f"Weak secondary raw-XGBoost serving percentile {value:.3f}; calibrated output excluded."
            if applies
            else "Cost-overrun prediction is outside this lifecycle."
        )
        for applies, value in zip(execution, serving.fillna(0.0))
    ]
    result["data_available"] = execution & serving.notna()
    return _finalize(result, COST_OVERRUN_PREDICTION)


def operational_trend_signal(spine: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    result = spine[["work_id"]].merge(context, on="work_id", how="left", validate="one_to_one")
    score = pd.to_numeric(result["operational_trend_context_score_0_100"], errors="coerce")
    supported = result["selected_trend_group"].notna() & ~result["selected_trend_group"].eq("NO_SUPPORTED_GROUP")
    flagged = as_bool(result["operational_trend_deviation_flag"])
    result["family_score_0_100"] = score.fillna(0.0)
    result["evidence_code"] = np.where(
        flagged, "OPERATIONAL_TREND_DEVIATION", "NO_OPERATIONAL_TREND_DEVIATION"
    )
    result["evidence_summary"] = [
        (
            f"{group} context; strongest metric {metric}; signed robust z {z:.3f}."
            if available and pd.notna(z)
            else "No sufficiently supported latest-month operational trend context."
        )
        for available, group, metric, z in zip(
            supported,
            result["selected_trend_group_value"],
            result["strongest_operational_trend_metric"],
            pd.to_numeric(result["strongest_operational_trend_robust_z"], errors="coerce"),
        )
    ]
    result["data_available"] = supported & result["strongest_operational_trend_robust_z"].notna()
    return _finalize(result, OPERATIONAL_TREND_CONTEXT)


def build_family_signals(
    features: pd.DataFrame,
    anomaly: pd.DataFrame,
    peer: pd.DataFrame,
    duplicates: pd.DataFrame,
    payment_summary: pd.DataFrame,
    payment_evidence: pd.DataFrame,
    fund_progress: pd.DataFrame,
    compliance_evidence: pd.DataFrame,
    predictive: pd.DataFrame,
    trend_context: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    spine = features[["work_id", "lifecycle_stage"]]
    signals = {
        ANOMALY: anomaly_signal(spine, anomaly),
        PEER_DEVIATION: peer_signal(spine, peer),
        DUPLICATE_REVIEW: duplicate_signal(spine, duplicates),
        PAYMENT_EXECUTION: payment_execution_signal(
            spine, payment_summary, payment_evidence, fund_progress
        ),
        OBSERVED_CONDITIONS: observed_conditions_signal(spine, features, predictive),
        COMPLIANCE: compliance_signal(spine, compliance_evidence),
        COST_OVERRUN_PREDICTION: cost_prediction_signal(spine, predictive),
        OPERATIONAL_TREND_CONTEXT: operational_trend_signal(spine, trend_context),
    }
    for family, frame in signals.items():
        if len(frame) != 3_000 or not frame["work_id"].is_unique:
            raise RuntimeError(f"{family} signal must contain 3,000 unique work IDs")
    return signals
