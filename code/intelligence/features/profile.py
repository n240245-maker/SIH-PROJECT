"""Reusable in-memory unified project profile for later APIs and explanations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from intelligence.data.loader import OperationalDataBundle

from .aggregations import (
    asset_records_as_of,
    progress_reports_as_of,
    released_payments_as_of,
)
from .builder import build_project_features


SAFE_WORK_CONTEXT_COLUMNS = [
    "work_id",
    "mp_id",
    "state_name",
    "constituency",
    "nodal_district",
    "district",
    "block",
    "village",
    "sector",
    "sub_sector",
    "work_description",
    "recommendation_date",
    "sanction_status",
    "implementing_agency_id",
    "expected_start_date",
    "expected_completion_date",
    "source_type",
    "source_reference",
    "synthetic_marker",
]


@dataclass(slots=True)
class ProjectProfile:
    work_context: dict[str, Any]
    mp_context: dict[str, Any]
    implementing_agency_context: dict[str, Any] | None
    released_payments_as_of: pd.DataFrame
    progress_reports_as_of: pd.DataFrame
    asset_records_as_of: pd.DataFrame
    derived_features: dict[str, Any]


def _single_record(frame: pd.DataFrame, field: str, value: Any) -> pd.Series:
    matched = frame.loc[frame[field].eq(value)]
    if len(matched) != 1:
        raise KeyError(f"Expected exactly one {field}={value!r}; found {len(matched)}")
    return matched.iloc[0]


def build_project_profile(
    work_id: str,
    bundle: OperationalDataBundle,
    as_of_date: date,
    *,
    feature_table: pd.DataFrame | None = None,
) -> ProjectProfile:
    """Connect one work to safe context, dated histories, assets, and features.

    No evaluation ground truth or unsafe official MP-name supplement is accepted
    by this API. Future payment/progress/closure events are excluded or masked.
    """

    work = _single_record(bundle.works, "work_id", work_id)
    mp = _single_record(bundle.mp, "mp_id", work["mp_id"])

    agency_context: dict[str, Any] | None = None
    agency_id = work["implementing_agency_id"]
    if pd.notna(agency_id):
        agency = _single_record(bundle.entities, "entity_id", agency_id)
        if agency["entity_type"] != "IMPLEMENTING_AGENCY":
            raise ValueError(f"{agency_id} is not an implementing agency")
        agency_context = agency.to_dict()

    payments = released_payments_as_of(bundle.payments, as_of_date)
    payments = payments.loc[payments["work_id"].eq(work_id)].reset_index(drop=True)
    progress = progress_reports_as_of(bundle.progress, as_of_date)
    progress = progress.loc[progress["work_id"].eq(work_id)].reset_index(drop=True)
    assets = asset_records_as_of(bundle.assets, as_of_date)
    assets = assets.loc[assets["work_id"].eq(work_id)].reset_index(drop=True)

    resolved_features = (
        build_project_features(bundle, as_of_date)
        if feature_table is None
        else feature_table
    )
    feature = _single_record(resolved_features, "work_id", work_id)
    feature_date = pd.Timestamp(feature["feature_snapshot_date"]).date()
    if feature_date != as_of_date:
        raise ValueError(
            f"Feature row snapshot {feature_date} does not match requested {as_of_date}"
        )

    work_context = work[SAFE_WORK_CONTEXT_COLUMNS].to_dict()
    as_of = pd.Timestamp(as_of_date)
    work_context["sanction_date_as_of"] = (
        work["sanction_date"]
        if pd.notna(work["sanction_date"]) and work["sanction_date"] <= as_of
        else pd.NaT
    )
    work_context["actual_start_date_as_of"] = (
        work["actual_start_date"]
        if pd.notna(work["actual_start_date"]) and work["actual_start_date"] <= as_of
        else pd.NaT
    )
    work_context["source_current_status"] = work["current_status"]
    work_context["source_current_physical_progress_pct"] = work[
        "current_physical_progress_pct"
    ]
    work_context["source_current_expenditure_inr"] = work["current_expenditure_inr"]

    return ProjectProfile(
        work_context=work_context,
        mp_context=mp.to_dict(),
        implementing_agency_context=agency_context,
        released_payments_as_of=payments,
        progress_reports_as_of=progress,
        asset_records_as_of=assets,
        derived_features=feature.to_dict(),
    )
