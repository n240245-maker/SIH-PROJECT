"""Deterministic weighted fusion with reconstructable family contributions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .policy import FAMILY_ORDER, LIFECYCLE_WEIGHTS, priority_band, validate_policy


EVIDENCE_COLUMNS = [
    "work_id",
    "lifecycle_stage",
    "family",
    "family_score_0_100",
    "family_weight_pct",
    "contribution_points",
    "source_artifact",
    "evidence_code",
    "evidence_summary",
    "data_available",
    "applicable",
]


def build_contribution_evidence(
    features: pd.DataFrame,
    signals: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    validate_policy()
    records: list[pd.DataFrame] = []
    for lifecycle, weights in LIFECYCLE_WEIGHTS.items():
        works = features.loc[
            features["lifecycle_stage"].eq(lifecycle), ["work_id", "lifecycle_stage"]
        ]
        for family, weight in weights.items():
            if family not in signals:
                raise ValueError(f"Missing family signal: {family}")
            evidence = works.merge(
                signals[family], on="work_id", how="left", validate="one_to_one"
            )
            if evidence["family_score_0_100"].isna().any():
                raise ValueError(f"{family} did not resolve for every {lifecycle} work")
            evidence["family_weight_pct"] = int(weight)
            evidence["contribution_points"] = (
                evidence["family_score_0_100"] * float(weight) / 100.0
            ).round(6)
            evidence["applicable"] = True
            records.append(evidence[EVIDENCE_COLUMNS])
    result = pd.concat(records, ignore_index=True)
    order = {family: index for index, family in enumerate(FAMILY_ORDER)}
    result["_family_order"] = result["family"].map(order)
    result = result.sort_values(
        ["work_id", "_family_order"], kind="stable"
    ).drop(columns="_family_order").reset_index(drop=True)
    return result


def _deterministic_ranks(scores: pd.DataFrame) -> pd.DataFrame:
    result = scores.copy()
    overall = result.sort_values(
        ["review_priority_score_0_100", "work_id"],
        ascending=[False, True],
        kind="stable",
    )
    result["review_priority_rank_overall"] = pd.Series(
        np.arange(1, len(overall) + 1, dtype="int64"), index=overall.index
    ).reindex(result.index).astype("int64")
    result["review_priority_rank_within_lifecycle"] = 0
    for _, index in result.groupby("lifecycle_stage", sort=False).groups.items():
        ranked = result.loc[index].sort_values(
            ["review_priority_score_0_100", "work_id"],
            ascending=[False, True],
            kind="stable",
        )
        result.loc[ranked.index, "review_priority_rank_within_lifecycle"] = np.arange(
            1, len(ranked) + 1, dtype="int64"
        )
    result["review_priority_rank_within_lifecycle"] = result[
        "review_priority_rank_within_lifecycle"
    ].astype("int64")
    return result


def build_review_priority_scores(
    features: pd.DataFrame,
    evidence: pd.DataFrame,
    duplicates: pd.DataFrame,
    payment_summary: pd.DataFrame,
    compliance_summary: pd.DataFrame,
    predictive: pd.DataFrame,
) -> pd.DataFrame:
    spine = features[["work_id", "lifecycle_stage"]].copy()
    aggregates = evidence.groupby("work_id", sort=False).agg(
        review_priority_score_0_100=("contribution_points", "sum"),
        _available_weight=(
            "family_weight_pct",
            lambda values: 0.0,
        ),
    )
    available_weight = (
        evidence.loc[evidence["data_available"].astype(bool)]
        .groupby("work_id")["family_weight_pct"]
        .sum()
    )
    aggregates["fusion_evidence_coverage_pct"] = aggregates.index.map(
        available_weight
    ).fillna(0.0)
    aggregates = aggregates.drop(columns="_available_weight").reset_index()
    scores = spine.merge(aggregates, on="work_id", how="left", validate="one_to_one")
    scores["review_priority_score_0_100"] = scores[
        "review_priority_score_0_100"
    ].round(6)
    scores["review_priority_band"] = scores["review_priority_score_0_100"].map(
        priority_band
    )
    scores = _deterministic_ranks(scores)

    family_order = {family: index for index, family in enumerate(FAMILY_ORDER)}
    top = evidence.copy()
    top["_family_order"] = top["family"].map(family_order)
    top = top.sort_values(
        ["work_id", "contribution_points", "_family_order"],
        ascending=[True, False, True],
        kind="stable",
    )
    top["_position"] = top.groupby("work_id").cumcount() + 1
    for position in (1, 2, 3):
        selected = top.loc[top["_position"].eq(position)].set_index("work_id")
        scores[f"top_contributor_{position}_family"] = scores["work_id"].map(selected["family"])
        scores[f"top_contributor_{position}_points"] = scores["work_id"].map(
            selected["contribution_points"]
        )
        scores[f"top_contributor_{position}_summary"] = scores["work_id"].map(
            selected["evidence_summary"]
        )

    scores = scores.merge(
        duplicates[["work_id", "review_candidate"]].rename(
            columns={"review_candidate": "has_duplicate_review_candidate"}
        ),
        on="work_id",
        how="left",
        validate="one_to_one",
    ).merge(
        payment_summary[["work_id", "has_payment_irregularity_evidence"]].rename(
            columns={"has_payment_irregularity_evidence": "has_payment_evidence"}
        ),
        on="work_id",
        how="left",
        validate="one_to_one",
    ).merge(
        compliance_summary[["work_id", "rules_review_count", "rules_non_compliant_count"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    ).merge(
        predictive[
            [
                "work_id",
                "already_overdue_as_of",
                "already_over_sanction_as_of",
                "cost_overrun_serving_percentile_0_100",
            ]
        ],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    scores["has_compliance_review"] = scores["rules_review_count"].fillna(0).gt(0)
    scores["has_deterministic_non_compliant_evidence"] = scores[
        "rules_non_compliant_count"
    ].fillna(0).gt(0)
    scores["cost_prediction_available"] = scores[
        "cost_overrun_serving_percentile_0_100"
    ].notna()
    scores = scores.drop(
        columns=[
            "rules_review_count",
            "rules_non_compliant_count",
            "cost_overrun_serving_percentile_0_100",
        ]
    )

    preferred = [
        "work_id",
        "lifecycle_stage",
        "review_priority_score_0_100",
        "review_priority_band",
        "review_priority_rank_overall",
        "review_priority_rank_within_lifecycle",
        "fusion_evidence_coverage_pct",
    ]
    for position in (1, 2, 3):
        preferred.extend(
            [
                f"top_contributor_{position}_family",
                f"top_contributor_{position}_points",
                f"top_contributor_{position}_summary",
            ]
        )
    preferred.extend(
        [
            "has_duplicate_review_candidate",
            "has_payment_evidence",
            "has_compliance_review",
            "has_deterministic_non_compliant_evidence",
            "already_overdue_as_of",
            "already_over_sanction_as_of",
            "cost_prediction_available",
        ]
    )
    scores = scores[preferred]
    if len(scores) != 3_000 or not scores["work_id"].is_unique:
        raise RuntimeError("Review-priority scores must contain 3,000 unique work IDs")
    if not scores["review_priority_score_0_100"].between(0, 100).all():
        raise RuntimeError("Review-priority score escaped 0-100")
    return scores


def build_review_priority_queue(scores: pd.DataFrame) -> pd.DataFrame:
    return scores.loc[scores["review_priority_band"].isin(["HIGH", "CRITICAL"])].sort_values(
        ["review_priority_score_0_100", "work_id"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)


def build_authority_summary(features: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    joined = features[["work_id", "state_name", "district", "sector"]].merge(
        scores[["work_id", "review_priority_score_0_100", "review_priority_band"]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    records: list[dict[str, object]] = []
    groups = {
        "STATE": ("state_name",),
        "DISTRICT": ("state_name", "district"),
        "SECTOR": ("sector",),
    }
    from intelligence.trends.monthly import encode_group_value

    for group_type, fields in groups.items():
        for keys, group in joined.groupby(list(fields), sort=True, dropna=False):
            key = keys[0] if isinstance(keys, tuple) and len(keys) == 1 else keys
            records.append(
                {
                    "group_type": group_type,
                    "group_value": encode_group_value(fields, key),
                    "work_count": int(len(group)),
                    "mean_review_priority": float(group["review_priority_score_0_100"].mean()),
                    "high_priority_count": int(group["review_priority_band"].eq("HIGH").sum()),
                    "critical_priority_count": int(group["review_priority_band"].eq("CRITICAL").sum()),
                }
            )
    return pd.DataFrame.from_records(records).sort_values(
        ["group_type", "group_value"], kind="stable"
    ).reset_index(drop=True)
