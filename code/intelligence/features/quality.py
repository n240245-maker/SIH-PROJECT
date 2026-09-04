"""Label-free feature-distribution audit for Day-3 selection decisions."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.paths import ProjectPaths

from .catalog import build_feature_catalog, feature_catalog_payload


NEAR_ZERO_DOMINANT_PERCENTAGE = 99.0
CANDIDATE_DATA_TYPES = {"integer", "float", "boolean"}


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.generic):
        return value.item()
    return value


def build_feature_quality_profile(
    features: pd.DataFrame,
    catalog: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Profile numeric/boolean fields without labels or feature-value mutation.

    Near-zero variance is defined as a non-constant field whose most common
    non-null value represents at least 99% of its non-null observations.
    """

    definitions = catalog or build_feature_catalog()
    by_name = {str(item["name"]): item for item in definitions}
    if list(by_name) != features.columns.tolist():
        raise ValueError("Feature catalog must exactly cover feature-table columns in order")

    profiles: list[dict[str, object]] = []
    for name, definition in by_name.items():
        data_type = str(definition["data_type"])
        if data_type not in CANDIDATE_DATA_TYPES:
            continue

        values = features[name].dropna()
        non_null_count = int(len(values))
        unique_count = int(values.nunique(dropna=True))
        counts = values.value_counts(dropna=False)
        dominant_count = int(counts.iloc[0]) if len(counts) else 0
        dominant_percentage = (
            100.0 * dominant_count / non_null_count if non_null_count else None
        )
        zero_variance = unique_count <= 1
        near_zero_variance = bool(
            not zero_variance
            and dominant_percentage is not None
            and dominant_percentage >= NEAR_ZERO_DOMINANT_PERCENTAGE
        )

        if data_type == "boolean":
            numeric_values = values.astype("boolean").astype("float64")
            minimum = bool(values.min()) if non_null_count else None
            maximum = bool(values.max()) if non_null_count else None
        else:
            numeric_values = pd.to_numeric(values, errors="raise").astype("float64")
            minimum = numeric_values.min() if non_null_count else None
            maximum = numeric_values.max() if non_null_count else None

        profiles.append(
            {
                "name": name,
                "category": definition["category"],
                "data_type": data_type,
                "model_eligible": bool(definition["model_eligible"]),
                "generic_anomaly_eligible": bool(
                    definition["generic_anomaly_eligible"]
                ),
                "non_null_count": non_null_count,
                "null_percentage": round(
                    100.0 * (len(features) - non_null_count) / max(1, len(features)),
                    6,
                ),
                "unique_count": unique_count,
                "minimum": _json_value(minimum),
                "maximum": _json_value(maximum),
                "mean": _json_value(numeric_values.mean()) if non_null_count else None,
                "standard_deviation": (
                    _json_value(numeric_values.std(ddof=1)) if non_null_count > 1 else None
                ),
                "dominant_value": _json_value(counts.index[0]) if len(counts) else None,
                "dominant_value_percentage": (
                    round(dominant_percentage, 6)
                    if dominant_percentage is not None
                    else None
                ),
                "zero_variance": bool(zero_variance),
                "near_zero_variance": near_zero_variance,
            }
        )

    zero_variance_features = [
        str(item["name"]) for item in profiles if item["zero_variance"]
    ]
    near_zero_variance_features = [
        str(item["name"]) for item in profiles if item["near_zero_variance"]
    ]
    return {
        "row_count": len(features),
        "audited_numeric_boolean_feature_count": len(profiles),
        "near_zero_variance_definition": (
            "Non-constant feature with one value representing at least 99% of "
            "non-null observations."
        ),
        "near_zero_dominant_percentage_threshold": NEAR_ZERO_DOMINANT_PERCENTAGE,
        "model_eligible_feature_count": sum(
            bool(item["model_eligible"]) for item in definitions
        ),
        "generic_anomaly_eligible_feature_count": sum(
            bool(item["generic_anomaly_eligible"]) for item in definitions
        ),
        "zero_variance_features": zero_variance_features,
        "near_zero_variance_features": near_zero_variance_features,
        "features": profiles,
    }


def write_feature_quality_profile(
    profile: dict[str, object],
    paths: ProjectPaths,
) -> Path:
    output_dir = paths.ensure_processed_data_dir().resolve()
    expected = (paths.project_root / "data" / "processed").resolve()
    if output_dir != expected:
        raise ValueError(f"Feature quality output must use {expected}, not {output_dir}")
    output_path = output_dir / "feature_quality_profile.json"
    output_path.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_refined_catalog(paths: ProjectPaths, as_of_date: date) -> Path:
    output_dir = paths.ensure_processed_data_dir().resolve()
    expected = (paths.project_root / "data" / "processed").resolve()
    if output_dir != expected:
        raise ValueError(f"Feature catalog output must use {expected}, not {output_dir}")
    output_path = output_dir / "feature_catalog.json"
    output_path.write_text(
        json.dumps(feature_catalog_payload(as_of_date), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    paths = ProjectPaths.discover()
    settings = load_settings(paths)
    feature_path = paths.processed_data_dir / "project_features.csv"
    if not feature_path.is_file():
        raise FileNotFoundError(f"Build Day-2 features first: {feature_path}")

    features = pd.read_csv(feature_path, encoding="utf-8", low_memory=False)
    catalog = build_feature_catalog()
    quality_profile = build_feature_quality_profile(features, catalog)
    catalog_path = write_refined_catalog(paths, settings.as_of_date)
    quality_path = write_feature_quality_profile(quality_profile, paths)
    print(f"Feature catalog: {catalog_path}")
    print(f"Feature quality profile: {quality_path}")
    print(
        json.dumps(
            {
                "audited_numeric_boolean_feature_count": quality_profile[
                    "audited_numeric_boolean_feature_count"
                ],
                "model_eligible_feature_count": quality_profile[
                    "model_eligible_feature_count"
                ],
                "generic_anomaly_eligible_feature_count": quality_profile[
                    "generic_anomaly_eligible_feature_count"
                ],
                "zero_variance_features": quality_profile["zero_variance_features"],
                "near_zero_variance_features": quality_profile[
                    "near_zero_variance_features"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
