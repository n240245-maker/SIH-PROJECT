"""Loader, schema, and ground-truth isolation tests."""

from __future__ import annotations

from dataclasses import fields
import inspect

import pandas as pd
import pytest

from intelligence.data.loader import (
    DataLoadError,
    OperationalDataBundle,
    load_evaluation_ground_truth,
    load_operational_data,
    validate_exact_columns,
)
from intelligence.data.schemas import OPERATIONAL_SCHEMAS


EXPECTED_ROWS = {
    "mp": 36,
    "entities": 108,
    "works": 3_000,
    "payments": 9_727,
    "progress": 14_902,
    "assets": 1_929,
}


def test_all_operational_files_load_with_expected_rows(operational_bundle):
    assert operational_bundle.row_counts == EXPECTED_ROWS
    assert operational_bundle.source_files == [
        "01_mp_master.csv",
        "02_agencies_vendors.csv",
        "03_works.csv",
        "04_payments.csv",
        "05_progress.csv",
        "06_assets_compliance.csv",
    ]


def test_operational_csv_headers_match_exact_schemas(project_paths):
    for schema in OPERATIONAL_SCHEMAS:
        header = pd.read_csv(
            project_paths.demo_data_dir / schema.filename,
            nrows=0,
            encoding="utf-8-sig",
        ).columns.tolist()
        assert header == schema.expected_columns


def test_changed_schema_is_rejected():
    schema = OPERATIONAL_SCHEMAS[0]
    with pytest.raises(DataLoadError, match="exact schema mismatch"):
        validate_exact_columns(schema.expected_columns[:-1], schema)
    with pytest.raises(DataLoadError, match="exact schema mismatch"):
        validate_exact_columns(schema.expected_columns + ["invented_column"], schema)


def test_required_dates_are_parsed_as_datetimes(operational_bundle):
    date_columns = {
        "mp": ["record_effective_date"],
        "works": [
            "recommendation_date",
            "sanction_date",
            "expected_start_date",
            "expected_completion_date",
            "actual_start_date",
        ],
        "payments": [
            "payment_request_date",
            "authorization_date",
            "payment_release_date",
        ],
        "progress": ["report_date"],
        "assets": [
            "completion_date",
            "completion_marked_date",
            "utilization_certificate_date",
            "handover_date",
            "public_use_date",
            "audit_date",
        ],
    }
    for table_name, columns in date_columns.items():
        frame = getattr(operational_bundle, table_name)
        for column in columns:
            assert pd.api.types.is_datetime64_any_dtype(frame[column]), (table_name, column)


def test_bundle_has_only_six_separate_operational_tables(operational_bundle):
    assert [field.name for field in fields(OperationalDataBundle)] == [
        "mp",
        "entities",
        "works",
        "payments",
        "progress",
        "assets",
    ]
    assert isinstance(operational_bundle.payments, pd.DataFrame)
    assert isinstance(operational_bundle.progress, pd.DataFrame)
    assert operational_bundle.payments is not operational_bundle.progress
    assert "ground_truth" not in dir(operational_bundle)
    assert "merged" not in dir(operational_bundle)


def test_ground_truth_requires_explicit_evaluation_loader(project_paths, operational_bundle):
    loader_source = inspect.getsource(load_operational_data)
    assert "ground_truth" not in loader_source
    evaluation = load_evaluation_ground_truth(project_paths)
    assert len(evaluation) == 3_000
    assert evaluation["work_id"].is_unique
    assert set(evaluation["work_id"]) == set(operational_bundle.works["work_id"])
