"""Transparent structured scoring of semantically retrieved work pairs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .similarity import (
    amount_similarity,
    date_proximity,
    geographic_distance_km,
    weighted_available_mean,
)


DUPLICATE_CANDIDATE_THRESHOLD = 75.0
REVIEW_MIN_SCORE = 90.0
REVIEW_MIN_TEXT_SIMILARITY = 0.97
REVIEW_MAX_DISTANCE_KM = 1.0
REVIEW_MIN_AMOUNT_SIMILARITY = 0.90
REVIEW_MAX_DATE_DIFFERENCE_DAYS = 120
DUPLICATE_SCORE_WEIGHTS: Mapping[str, float] = {
    "text_cosine_similarity": 0.50,
    "location_similarity": 0.15,
    "amount_similarity": 0.15,
    "date_proximity": 0.10,
    "sector_match": 0.05,
    "sub_sector_match": 0.03,
    "implementing_agency_match": 0.02,
}

SAFE_STRUCTURED_COLUMNS = (
    "work_id",
    "state_name",
    "district",
    "block",
    "village",
    "latitude",
    "longitude",
    "recommended_amount_inr",
    "sanctioned_amount_inr",
    "recommendation_date",
    "sector",
    "sub_sector",
    "implementing_agency_id",
)


def _normalized_equal(first: object, second: object) -> bool:
    if first is None or second is None or pd.isna(first) or pd.isna(second):
        return False
    return str(first).strip().casefold() == str(second).strip().casefold()


def _location_similarity(
    *,
    same_state: bool,
    same_district: bool,
    same_block: bool,
    same_village: bool,
    distance_km: float | None,
) -> float | None:
    distance_proximity = (
        max(0.0, 1.0 - distance_km / 25.0) if distance_km is not None else None
    )
    return weighted_available_mean(
        (
            (float(same_state), 0.40),
            (float(same_district), 0.25),
            (float(same_block), 0.15),
            (float(same_village), 0.10),
            (distance_proximity, 0.10),
        )
    )


def duplicate_priority_score(components: Mapping[str, float | None]) -> float:
    """Weighted available-evidence score, returned on a 0–100 scale."""

    weighted = [
        (components.get(name), weight)
        for name, weight in DUPLICATE_SCORE_WEIGHTS.items()
    ]
    mean = weighted_available_mean(weighted)
    if mean is None:
        raise ValueError("A duplicate pair has no usable scoring evidence")
    return float(np.clip(100.0 * mean, 0.0, 100.0))


def duplicate_review_policy(evidence: Mapping[str, object]) -> tuple[bool, str]:
    """Select a small review queue using semantic and structured corroboration.

    The policy is intentionally independent of evaluation labels.  It requires a
    high composite score plus strong semantic similarity, precise local agreement,
    geographic proximity, amount similarity, temporal proximity, and matching
    sector taxonomy.  Failure reasons make the queue boundary auditable.
    """

    distance = evidence.get("geographic_distance_km")
    amount = evidence.get("amount_similarity")
    date_difference = evidence.get("recommendation_date_difference_days")
    checks = (
        (
            "score_below_90",
            float(evidence["duplicate_similarity_score_0_100"]) >= REVIEW_MIN_SCORE,
        ),
        (
            "text_similarity_below_0.97",
            float(evidence["text_cosine_similarity"])
            >= REVIEW_MIN_TEXT_SIMILARITY,
        ),
        ("district_differs", bool(evidence["same_district"])),
        ("block_differs", bool(evidence["same_block"])),
        ("village_differs", bool(evidence["same_village"])),
        (
            "distance_missing_or_above_1km",
            distance is not None
            and not pd.isna(distance)
            and float(distance) <= REVIEW_MAX_DISTANCE_KM,
        ),
        (
            "amount_similarity_missing_or_below_0.90",
            amount is not None
            and not pd.isna(amount)
            and float(amount) >= REVIEW_MIN_AMOUNT_SIMILARITY,
        ),
        (
            "date_difference_missing_or_above_120_days",
            date_difference is not None
            and not pd.isna(date_difference)
            and int(date_difference) <= REVIEW_MAX_DATE_DIFFERENCE_DAYS,
        ),
        ("sector_differs", bool(evidence["sector_match"])),
        ("sub_sector_differs", bool(evidence["sub_sector_match"])),
    )
    failed = [reason for reason, passed in checks if not passed]
    if failed:
        return False, "NOT_SELECTED:" + ",".join(failed)
    return True, "SELECTED:semantic+locality+distance+amount+date+taxonomy"


def build_duplicate_candidates(
    works: pd.DataFrame,
    retrieved_pairs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add independent structured evidence and a deterministic review score."""

    missing = sorted(set(SAFE_STRUCTURED_COLUMNS).difference(works.columns))
    if missing:
        raise ValueError(f"Structured duplicate fields missing from works: {missing}")
    safe_works = works.loc[:, SAFE_STRUCTURED_COLUMNS].copy().set_index("work_id")
    if not safe_works.index.is_unique:
        raise ValueError("Work IDs must be unique")

    records: list[dict[str, Any]] = []
    for pair in retrieved_pairs.itertuples(index=False):
        first = safe_works.loc[pair.work_id_a]
        second = safe_works.loc[pair.work_id_b]
        same_state = _normalized_equal(first["state_name"], second["state_name"])
        same_district = _normalized_equal(first["district"], second["district"])
        same_block = _normalized_equal(first["block"], second["block"])
        same_village = _normalized_equal(first["village"], second["village"])
        sector_match = _normalized_equal(first["sector"], second["sector"])
        sub_sector_match = _normalized_equal(first["sub_sector"], second["sub_sector"])
        agency_match = _normalized_equal(
            first["implementing_agency_id"], second["implementing_agency_id"]
        )
        distance_km = geographic_distance_km(
            first["latitude"],
            first["longitude"],
            second["latitude"],
            second["longitude"],
        )
        recommended_similarity = amount_similarity(
            first["recommended_amount_inr"], second["recommended_amount_inr"]
        )
        sanctioned_similarity = amount_similarity(
            first["sanctioned_amount_inr"], second["sanctioned_amount_inr"]
        )
        combined_amount_similarity = weighted_available_mean(
            ((recommended_similarity, 0.6), (sanctioned_similarity, 0.4))
        )
        date_difference, date_similarity = date_proximity(
            first["recommendation_date"], second["recommendation_date"]
        )
        location_similarity = _location_similarity(
            same_state=same_state,
            same_district=same_district,
            same_block=same_block,
            same_village=same_village,
            distance_km=distance_km,
        )
        components = {
            "text_cosine_similarity": float(pair.text_cosine_similarity),
            "location_similarity": location_similarity,
            "amount_similarity": combined_amount_similarity,
            "date_proximity": date_similarity,
            "sector_match": float(sector_match),
            "sub_sector_match": float(sub_sector_match),
            "implementing_agency_match": float(agency_match),
        }
        score = duplicate_priority_score(components)
        candidate_flag = bool(score >= DUPLICATE_CANDIDATE_THRESHOLD)
        distance_text = "missing" if distance_km is None else f"{distance_km:.3f}"
        record: dict[str, Any] = {
                "pair_id": f"{pair.work_id_a}__{pair.work_id_b}",
                "work_id_a": pair.work_id_a,
                "work_id_b": pair.work_id_b,
                "duplicate_similarity_score_0_100": round(score, 6),
                "text_cosine_similarity": round(float(pair.text_cosine_similarity), 8),
                "geographic_distance_km": distance_km,
                "location_similarity": location_similarity,
                "recommended_amount_similarity": recommended_similarity,
                "sanctioned_amount_similarity": sanctioned_similarity,
                "amount_similarity": combined_amount_similarity,
                "recommendation_date_difference_days": date_difference,
                "date_proximity_score": date_similarity,
                "same_state": same_state,
                "same_district": same_district,
                "same_block": same_block,
                "same_village": same_village,
                "sector_match": sector_match,
                "sub_sector_match": sub_sector_match,
                "implementing_agency_match": agency_match,
                "candidate_flag": candidate_flag,
                "retrieval_candidate": True,
                "evidence_summary": (
                    f"semantic={float(pair.text_cosine_similarity):.3f}; "
                    f"same_district={str(same_district).lower()}; "
                    f"same_block={str(same_block).lower()}; "
                    f"same_village={str(same_village).lower()}; "
                    f"distance_km={distance_text}; "
                    f"amount_similarity={combined_amount_similarity:.3f}; "
                    f"date_difference_days={date_difference}"
                ),
            }
        review_candidate, review_policy_reason = duplicate_review_policy(record)
        record["review_candidate"] = review_candidate
        record["review_policy_reason"] = review_policy_reason
        records.append(record)

    candidates = pd.DataFrame.from_records(records).sort_values(
        ["duplicate_similarity_score_0_100", "pair_id"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    if candidates["pair_id"].duplicated().any():
        raise RuntimeError("Duplicate candidate pair IDs are not unique")

    flagged = candidates.loc[candidates["candidate_flag"]]
    work_ids = works["work_id"].astype(str)
    links = pd.concat(
        [
            flagged.rename(
                columns={"work_id_a": "work_id", "work_id_b": "candidate_work_id"}
            ),
            flagged.rename(
                columns={"work_id_b": "work_id", "work_id_a": "candidate_work_id"}
            ),
        ],
        ignore_index=True,
    ) if not flagged.empty else pd.DataFrame(
        columns=["work_id", "candidate_work_id", "duplicate_similarity_score_0_100"]
    )
    summary = pd.DataFrame({"work_id": work_ids})
    if not links.empty:
        ordered_links = links.sort_values(
            ["work_id", "duplicate_similarity_score_0_100", "candidate_work_id"],
            ascending=[True, False, True],
            kind="stable",
        )
        counts = ordered_links.groupby("work_id").size()
        best = ordered_links.drop_duplicates("work_id", keep="first").set_index("work_id")
        summary["duplicate_candidate_count"] = summary["work_id"].map(counts).fillna(0).astype("int64")
        summary["best_duplicate_candidate_work_id"] = summary["work_id"].map(best["candidate_work_id"])
        summary["best_duplicate_similarity_score_0_100"] = summary["work_id"].map(
            best["duplicate_similarity_score_0_100"]
        )
    else:
        summary["duplicate_candidate_count"] = 0
        summary["best_duplicate_candidate_work_id"] = pd.NA
        summary["best_duplicate_similarity_score_0_100"] = np.nan

    review_flagged = candidates.loc[candidates["review_candidate"]]
    review_links = pd.concat(
        [
            review_flagged.rename(
                columns={"work_id_a": "work_id", "work_id_b": "candidate_work_id"}
            ),
            review_flagged.rename(
                columns={"work_id_b": "work_id", "work_id_a": "candidate_work_id"}
            ),
        ],
        ignore_index=True,
    ) if not review_flagged.empty else pd.DataFrame(
        columns=["work_id", "candidate_work_id", "duplicate_similarity_score_0_100"]
    )
    if not review_links.empty:
        ordered_review_links = review_links.sort_values(
            ["work_id", "duplicate_similarity_score_0_100", "candidate_work_id"],
            ascending=[True, False, True],
            kind="stable",
        )
        review_counts = ordered_review_links.groupby("work_id").size()
        best_review = ordered_review_links.drop_duplicates(
            "work_id", keep="first"
        ).set_index("work_id")
        summary["review_candidate_count"] = (
            summary["work_id"].map(review_counts).fillna(0).astype("int64")
        )
        summary["best_review_candidate_work_id"] = summary["work_id"].map(
            best_review["candidate_work_id"]
        )
        summary["best_review_similarity_score_0_100"] = summary["work_id"].map(
            best_review["duplicate_similarity_score_0_100"]
        )
    else:
        summary["review_candidate_count"] = 0
        summary["best_review_candidate_work_id"] = pd.NA
        summary["best_review_similarity_score_0_100"] = np.nan
    summary["review_candidate"] = summary["review_candidate_count"].gt(0)
    return candidates, summary
