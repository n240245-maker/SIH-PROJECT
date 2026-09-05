"""Read-only indexed access to generated demo-v2 operational artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.serialization import json_safe
from intelligence.data.paths import ProjectPaths
from intelligence.v2.loader import load_v2_serving_data, v2_models_dir, v2_processed_dir


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json_safe(frame.to_dict(orient="records"))


class V2ArtifactRepository:
    """Loads demo-v2 data without importing the evaluation-only label table."""

    def __init__(self, paths: ProjectPaths | None = None) -> None:
        self.paths = paths or ProjectPaths.discover()
        self.data = load_v2_serving_data(self.paths)
        processed = v2_processed_dir(self.paths)
        models = v2_models_dir(self.paths)
        required = [
            "work_profile.csv", "review_priority_scores.csv", "review_priority_evidence.csv",
            "review_alerts.csv", "anomaly_scores.csv", "duplicate_candidates.csv",
            "duplicate_summary.csv", "cost_overrun_scores.csv", "geo_evidence_status.csv",
            "record_status.csv", "risk_fusion_policy.json", "manifest.json",
            "evaluation/cost_model_evaluation.json", "evaluation/anomaly_evaluation.json",
            "evaluation/duplicate_evaluation.json",
        ]
        missing = [name for name in required if not (processed / name).is_file()]
        if missing:
            raise RuntimeError(f"Missing demo-v2 generated artifacts: {missing}")

        self.profile = pd.read_csv(processed / "work_profile.csv", low_memory=False)
        if len(self.profile) != int(self.data.metadata["work_count"]) or not self.profile["work_id"].is_unique:
            raise RuntimeError("demo-v2 work profile must contain one row per work")
        self.work_ids = frozenset(self.profile["work_id"].astype(str))
        self._work_positions = {
            str(work_id): position
            for position, work_id in enumerate(self.profile["work_id"])
        }
        self.mp_index = {
            str(row["mp_id"]): json_safe(row)
            for row in self.data.mps.to_dict(orient="records")
        }
        self.entity_index = {
            str(row["entity_id"]): json_safe(row)
            for row in self.data.entities.to_dict(orient="records")
        }
        # Keep each one-to-many table once. Materializing nested dictionaries of
        # every row roughly doubled the serving footprint and exceeded the 512 MB
        # production instance when the baseline repository was also resident.
        self._group_frames = {
            "payments": self.data.payments,
            "progress": self.data.progress,
            "records": self.data.records,
            "geo": self.data.geo_evidence,
            "alerts": pd.read_csv(processed / "review_alerts.csv"),
            "priority_evidence": pd.read_csv(processed / "review_priority_evidence.csv"),
        }
        candidates = pd.read_csv(processed / "duplicate_candidates.csv")
        candidates = candidates.loc[candidates["review_candidate"].astype(str).str.casefold().eq("true")]
        self.duplicate_pairs: dict[str, list[dict[str, Any]]] = {}
        for item in _records(candidates):
            for work_id in (str(item["work_id_a"]), str(item["work_id_b"])):
                self.duplicate_pairs.setdefault(work_id, []).append(item)
        self.allocations = self.data.allocations
        self.policy = self._load_json(processed / "risk_fusion_policy.json")
        self.manifest = self._load_json(processed / "manifest.json")
        self.cost_evaluation = self._load_json(processed / "evaluation" / "cost_model_evaluation.json")
        self.anomaly_evaluation = self._load_json(processed / "evaluation" / "anomaly_evaluation.json")
        self.duplicate_evaluation = self._load_json(processed / "evaluation" / "duplicate_evaluation.json")
        self.dataset_metadata = self.data.metadata
        baseline_processed = self.paths.project_root / "data" / "processed"
        self.guideline_chunks = self._load_json(baseline_processed / "guideline_chunks.json")
        self.guideline_manifest = self._load_json(baseline_processed / "guideline_manifest.json")
        self.models_dir = models

    @staticmethod
    def _load_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def require_work(self, work_id: str) -> dict[str, Any]:
        try:
            position = self._work_positions[work_id]
        except KeyError:
            raise KeyError(work_id) from None
        return json_safe(self.profile.iloc[position].to_dict())

    def group(self, name: str, work_id: str) -> list[dict[str, Any]]:
        frame = self._group_frames[name]
        return _records(frame.loc[frame["work_id"].eq(work_id)])

    def rows_for_work_ids(self, name: str, work_ids: set[str]) -> list[dict[str, Any]]:
        """Return bounded evidence without building a permanent nested copy."""

        frame = self._group_frames[name]
        return _records(frame.loc[frame["work_id"].isin(work_ids)])

    def image_path(self, relative_path: str) -> Path:
        candidate = (self.paths.project_root / "data" / "Demo-data-v2" / relative_path).resolve()
        root = (self.paths.project_root / "data" / "Demo-data-v2").resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise FileNotFoundError(relative_path)
        return candidate
