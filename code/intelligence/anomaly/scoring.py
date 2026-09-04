"""Governed detector outputs and statistical evidence context."""

from __future__ import annotations

import pandas as pd


ANOMALY_SCORE_COLUMNS = (
    "work_id",
    "lifecycle_stage",
    "iforest_score_samples_raw",
    "iforest_unusualness_score",
    "within_stage_anomaly_percentile_0_100",
    "within_stage_rank",
    "stage_population",
    "peer_outlier_count",
    "max_abs_peer_deviation",
    "top_peer_deviation_metric",
)


def attach_peer_context(
    isolation_scores: pd.DataFrame,
    peer_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Attach separate peer context without combining detector signals."""

    context = peer_summary.loc[
        :,
        [
            "work_id",
            "peer_outlier_count",
            "max_abs_peer_deviation",
            "top_peer_deviation_metric",
        ],
    ]
    scores = isolation_scores.merge(
        context,
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    if len(scores) != len(isolation_scores) or not scores["work_id"].is_unique:
        raise ValueError("Anomaly scores lost one-row-per-work cardinality")
    return scores.loc[:, ANOMALY_SCORE_COLUMNS]


def build_anomaly_evidence(
    anomaly_scores: pd.DataFrame,
    peer_evidence: pd.DataFrame,
) -> pd.DataFrame:
    """Select each work's strongest available statistical peer deviation.

    These rows accompany the model score. They are not causal explanations or
    feature contributions from Isolation Forest.
    """

    strongest = (
        peer_evidence.dropna(subset=["robust_deviation"])
        .sort_values(
            ["work_id", "absolute_robust_deviation", "metric"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates("work_id", keep="first")
    )
    evidence_columns = [
        "work_id",
        "metric",
        "observed_value",
        "peer_median",
        "peer_mad",
        "peer_iqr",
        "peer_p10",
        "peer_p90",
        "robust_deviation",
        "absolute_robust_deviation",
        "deviation_method",
        "peer_group_level",
        "peer_group_size",
        "statistical_peer_outlier",
        "direction",
    ]
    output = anomaly_scores.merge(
        strongest.loc[:, evidence_columns],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    output.insert(
        len(output.columns),
        "evidence_interpretation",
        (
            "Statistical peer evidence accompanying the anomaly score; not an "
            "Isolation Forest feature contribution."
        ),
    )
    return output
