"""Machine-readable validation report writers."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .paths import ProjectPaths
from .validation import ValidationResult


ISSUE_COLUMNS = [
    "issue_code",
    "severity",
    "file_or_table",
    "record_id",
    "work_id",
    "field",
    "observed_value",
    "expected_condition",
    "message",
    "details_json",
]


def _assert_processed_output(paths: ProjectPaths) -> Path:
    expected = (paths.project_root / "data" / "processed").resolve()
    actual = paths.processed_data_dir.resolve()
    if actual != expected:
        raise ValueError(f"Validation outputs must use {expected}, not {actual}")
    return paths.ensure_processed_data_dir().resolve()


def write_validation_outputs(
    result: ValidationResult,
    paths: ProjectPaths | None = None,
) -> tuple[Path, Path]:
    """Write only validation_summary.json and validation_issues.csv under data/processed."""

    resolved_paths = paths or ProjectPaths.discover()
    output_dir = _assert_processed_output(resolved_paths)
    summary_path = output_dir / "validation_summary.json"
    issues_path = output_dir / "validation_issues.csv"

    summary_path.write_text(
        json.dumps(result.summary_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    issue_records: list[dict[str, object]] = []
    for issue in result.issues:
        record = issue.model_dump(mode="json")
        record["severity"] = issue.severity.value
        record["details_json"] = json.dumps(record.pop("details"), sort_keys=True, ensure_ascii=False)
        issue_records.append(record)
    pd.DataFrame(issue_records, columns=ISSUE_COLUMNS).to_csv(
        issues_path,
        index=False,
        encoding="utf-8",
    )
    return summary_path, issues_path
