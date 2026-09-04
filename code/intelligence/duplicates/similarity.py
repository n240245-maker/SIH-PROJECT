"""Cosine retrieval and safe structured similarity helpers."""

from __future__ import annotations

from collections.abc import Sequence
import math

from geopy.distance import geodesic
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors


TOP_NEIGHBORS_PER_WORK = 10


def amount_similarity(first: object, second: object) -> float | None:
    """Bounded symmetric amount similarity, null when values are unusable."""

    if first is None or second is None or pd.isna(first) or pd.isna(second):
        return None
    first_value = float(first)
    second_value = float(second)
    denominator = max(abs(first_value), abs(second_value))
    if denominator <= 0:
        return 1.0 if first_value == second_value else None
    return float(np.clip(1.0 - abs(first_value - second_value) / denominator, 0.0, 1.0))


def geographic_distance_km(
    latitude_a: object,
    longitude_a: object,
    latitude_b: object,
    longitude_b: object,
) -> float | None:
    """Return WGS-84 geodesic distance; missing/invalid coordinates stay null."""

    coordinates = (latitude_a, longitude_a, latitude_b, longitude_b)
    if any(value is None or pd.isna(value) for value in coordinates):
        return None
    lat_a, lon_a, lat_b, lon_b = map(float, coordinates)
    if not (-90 <= lat_a <= 90 and -90 <= lat_b <= 90):
        return None
    if not (-180 <= lon_a <= 180 and -180 <= lon_b <= 180):
        return None
    return float(geodesic((lat_a, lon_a), (lat_b, lon_b)).kilometers)


def date_proximity(date_a: object, date_b: object) -> tuple[int | None, float | None]:
    """Return absolute day difference and a transparent one-year proximity score."""

    if date_a is None or date_b is None or pd.isna(date_a) or pd.isna(date_b):
        return None, None
    difference = abs((pd.Timestamp(date_a) - pd.Timestamp(date_b)).days)
    return int(difference), float(max(0.0, 1.0 - difference / 365.0))


def weighted_available_mean(values: Sequence[tuple[float | None, float]]) -> float | None:
    """Average available evidence without treating missing inputs as zero."""

    available = [(float(value), weight) for value, weight in values if value is not None]
    denominator = sum(weight for _, weight in available)
    if denominator <= 0:
        return None
    return float(sum(value * weight for value, weight in available) / denominator)


def retrieve_cosine_candidate_pairs(
    embeddings: np.ndarray,
    work_ids: Sequence[str],
    *,
    top_neighbors: int = TOP_NEIGHBORS_PER_WORK,
) -> pd.DataFrame:
    """Retrieve local nearest neighbors and canonicalize each pair once."""

    if embeddings.ndim != 2 or embeddings.shape[0] != len(work_ids):
        raise ValueError("Embeddings must contain exactly one row per work ID")
    if len(set(work_ids)) != len(work_ids):
        raise ValueError("Work IDs must be unique for candidate retrieval")
    if len(work_ids) < 2:
        return pd.DataFrame(columns=["work_id_a", "work_id_b", "text_cosine_similarity"])

    neighbor_count = min(len(work_ids), top_neighbors + 1)
    index = NearestNeighbors(
        n_neighbors=neighbor_count,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    ).fit(embeddings)
    distances, neighbors = index.kneighbors(embeddings, return_distance=True)

    rows: list[dict[str, object]] = []
    for source_index, (source_distances, source_neighbors) in enumerate(
        zip(distances, neighbors, strict=True)
    ):
        source_id = str(work_ids[source_index])
        retained = 0
        for distance, neighbor_index in zip(
            source_distances, source_neighbors, strict=True
        ):
            neighbor_id = str(work_ids[int(neighbor_index)])
            if neighbor_id == source_id:
                continue
            work_id_a, work_id_b = sorted((source_id, neighbor_id))
            rows.append(
                {
                    "work_id_a": work_id_a,
                    "work_id_b": work_id_b,
                    "text_cosine_similarity": float(
                        np.clip(1.0 - float(distance), 0.0, 1.0)
                    ),
                }
            )
            retained += 1
            if retained >= top_neighbors:
                break

    pairs = pd.DataFrame.from_records(rows)
    pairs = (
        pairs.groupby(["work_id_a", "work_id_b"], as_index=False, sort=True)[
            "text_cosine_similarity"
        ]
        .max()
        .sort_values(["work_id_a", "work_id_b"], kind="stable")
        .reset_index(drop=True)
    )
    if pairs[["work_id_a", "work_id_b"]].duplicated().any():
        raise RuntimeError("Canonical duplicate pairs are not unique")
    if pairs["work_id_a"].eq(pairs["work_id_b"]).any():
        raise RuntimeError("Self-pairs must not enter duplicate candidates")
    return pairs
