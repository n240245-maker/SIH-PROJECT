"""Profile-isolated loaders and integrity checks for the synthetic v2 dataset."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from intelligence.data.paths import ProjectPaths


@dataclass(slots=True)
class V2DataBundle:
    mps: pd.DataFrame
    entities: pd.DataFrame
    works: pd.DataFrame
    payments: pd.DataFrame
    progress: pd.DataFrame
    assets: pd.DataFrame
    records: pd.DataFrame
    allocations: pd.DataFrame
    geo_evidence: pd.DataFrame
    metadata: dict

    @property
    def row_counts(self) -> dict[str, int]:
        return {
            name: len(getattr(self, name))
            for name in (
                "mps", "entities", "works", "payments", "progress",
                "assets", "records", "allocations", "geo_evidence",
            )
        }


@dataclass(slots=True)
class V2ServingDataBundle:
    """Minimum operational tables required by the demo-v2 API.

    The generated one-row-per-work profile replaces the raw works table for
    serving. Assets are already represented by governed profile fields, so
    neither large source table is retained in the web process.
    """

    mps: pd.DataFrame
    entities: pd.DataFrame
    payments: pd.DataFrame
    progress: pd.DataFrame
    records: pd.DataFrame
    allocations: pd.DataFrame
    geo_evidence: pd.DataFrame
    metadata: dict


def v2_data_dir(paths: ProjectPaths | None = None) -> Path:
    resolved = paths or ProjectPaths.discover()
    return resolved.project_root / "data" / "Demo-data-v2"


def v2_processed_dir(paths: ProjectPaths | None = None) -> Path:
    resolved = paths or ProjectPaths.discover()
    return resolved.project_root / "data" / "processed-v2"


def v2_models_dir(paths: ProjectPaths | None = None) -> Path:
    resolved = paths or ProjectPaths.discover()
    return resolved.project_root / "models" / "v2"


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)


def load_v2_data(paths: ProjectPaths | None = None) -> V2DataBundle:
    """Load operational data only; evaluation ground truth is deliberately excluded."""

    data = v2_data_dir(paths)
    metadata = json.loads((data / "dataset_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("synthetic_demo_data") is not True:
        raise RuntimeError("demo_v2 metadata must explicitly identify synthetic data")
    return V2DataBundle(
        mps=_read(data / "01_mp_master.csv"),
        entities=_read(data / "02_entities.csv"),
        works=_read(data / "03_works.csv"),
        payments=_read(data / "04_payments.csv"),
        progress=_read(data / "05_progress.csv"),
        assets=_read(data / "06_assets.csv"),
        records=_read(data / "10_work_records.csv"),
        allocations=_read(data / "11_annual_allocations.csv"),
        geo_evidence=_read(data / "12_geo_site_evidence.csv"),
        metadata=metadata,
    )


def load_v2_serving_data(paths: ProjectPaths | None = None) -> V2ServingDataBundle:
    """Load only the operational source tables required by the v2 API."""

    data = v2_data_dir(paths)
    metadata = json.loads((data / "dataset_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("synthetic_demo_data") is not True:
        raise RuntimeError("demo_v2 metadata must explicitly identify synthetic data")
    return V2ServingDataBundle(
        mps=_read(data / "01_mp_master.csv"),
        entities=_read(data / "02_entities.csv"),
        payments=_read(data / "04_payments.csv"),
        progress=_read(data / "05_progress.csv"),
        records=_read(data / "10_work_records.csv"),
        allocations=_read(data / "11_annual_allocations.csv"),
        geo_evidence=_read(data / "12_geo_site_evidence.csv"),
        metadata=metadata,
    )


def load_v2_evaluation_ground_truth(paths: ProjectPaths | None = None) -> pd.DataFrame:
    """EVALUATION ONLY. Production loaders and services must never call this function."""

    return _read(v2_data_dir(paths) / "evaluation" / "anomaly_ground_truth_v2.csv")


def verify_v2_integrity(paths: ProjectPaths | None = None) -> dict[str, object]:
    data = v2_data_dir(paths)
    manifest = _read(data / "00_manifest.csv")
    hash_failures: list[str] = []
    row_failures: list[str] = []
    for row in manifest.to_dict(orient="records"):
        path = data / str(row["file_name"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(row["sha256"]):
            hash_failures.append(str(row["file_name"]))
        expected_rows = int(row["row_count"])
        if path.suffix.casefold() == ".csv":
            actual_rows = len(_read(path))
            if actual_rows != expected_rows:
                row_failures.append(str(row["file_name"]))

    bundle = load_v2_data(paths)
    key_checks = {
        "work_id_unique": bundle.works["work_id"].is_unique,
        "payment_id_unique": bundle.payments["payment_id"].is_unique,
        "progress_id_unique": bundle.progress["progress_id"].is_unique,
        "record_id_unique": bundle.records["record_id"].is_unique,
        "evidence_id_unique": bundle.geo_evidence["evidence_id"].is_unique,
    }
    work_ids = set(bundle.works["work_id"].astype(str))
    foreign_key_checks = {
        "payments_to_works": set(bundle.payments["work_id"].astype(str)) <= work_ids,
        "progress_to_works": set(bundle.progress["work_id"].astype(str)) <= work_ids,
        "records_to_works": set(bundle.records["work_id"].astype(str)) <= work_ids,
        "geo_to_works": set(bundle.geo_evidence["work_id"].astype(str)) <= work_ids,
        "works_to_mps": set(bundle.works["mp_id"].astype(str)) <= set(bundle.mps["mp_id"].astype(str)),
        "works_to_agencies": set(bundle.works["implementing_agency_id"].astype(str)) <= set(bundle.entities["entity_id"].astype(str)),
    }
    failures = hash_failures + row_failures + [key for key, value in {**key_checks, **foreign_key_checks}.items() if not value]
    return {
        "status": "PASS" if not failures else "FAIL",
        "hash_failures": hash_failures,
        "row_count_failures": row_failures,
        "key_checks": key_checks,
        "foreign_key_checks": foreign_key_checks,
        "row_counts": bundle.row_counts,
        "ground_truth_loaded_by_operational_loader": False,
    }
