"""Startup-validated, cached views over frozen Day 2--8.2 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from intelligence.data.paths import ProjectPaths

from backend.serialization import json_safe


CORE_WORK_FILES = {
    "features": "project_features.csv",
    "priority": "review_priority_scores.csv",
    "anomaly": "anomaly_scores.csv",
    "peer_summary": "peer_benchmark_summary.csv",
    "duplicate_summary": "duplicate_summary.csv",
    "payment_summary": "payment_irregularity_summary.csv",
    "compliance_summary": "compliance_summary.csv",
    "prediction": "predictive_scores.csv",
    "trend_context": "work_trend_context.csv",
}

GROUP_FILES = {
    "contributions": "review_priority_evidence.csv",
    "alerts": "review_alerts.csv",
    "peer_evidence": "peer_benchmark_evidence.csv",
    "payment_evidence": "payment_irregularities.csv",
    "compliance_evidence": "compliance_evidence.csv",
    "prediction_explanations": "predictive_explanations.csv",
}


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json_safe(frame.to_dict(orient="records"))


class ApplicationArtifactRepository:
    """Loads governed artifacts once and creates bounded lookup indexes."""

    def __init__(self, paths: ProjectPaths | None = None) -> None:
        self.paths = paths or ProjectPaths.discover()
        processed = self.paths.processed_data_dir
        required = [
            *CORE_WORK_FILES.values(),
            *GROUP_FILES.values(),
            "review_priority_queue.csv",
            "duplicate_candidates.csv",
            "fund_progress_evidence.csv",
            "trend_timeseries.csv",
            "trend_alerts.csv",
            "detector_hotspots.csv",
            "review_priority_authority_summary.csv",
            "risk_fusion_policy.json",
            "guideline_manifest.json",
            "guideline_chunks.json",
            "explanation_context.jsonl",
            "day8_rag_summary.json",
        ]
        missing = [name for name in required if not (processed / name).is_file()]
        if missing:
            raise RuntimeError(f"Missing critical frozen artifacts: {missing}")

        self.frames: dict[str, pd.DataFrame] = {
            name: pd.read_csv(processed / filename, low_memory=False)
            for name, filename in CORE_WORK_FILES.items()
        }
        expected_ids: set[str] | None = None
        for name, frame in self.frames.items():
            if len(frame) != 3_000 or not frame["work_id"].is_unique:
                raise RuntimeError(
                    f"{CORE_WORK_FILES[name]} must contain 3,000 unique work IDs"
                )
            ids = set(frame["work_id"].astype(str))
            if expected_ids is None:
                expected_ids = ids
            elif ids != expected_ids:
                raise RuntimeError(f"{CORE_WORK_FILES[name]} work IDs do not align")
        self.work_ids = frozenset(expected_ids or set())

        self.single: dict[str, dict[str, dict[str, Any]]] = {}
        for name, frame in self.frames.items():
            self.single[name] = {
                str(row["work_id"]): json_safe(row)
                for row in frame.to_dict(orient="records")
            }

        self.groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.group_frames: dict[str, pd.DataFrame] = {}
        for name, filename in GROUP_FILES.items():
            frame = pd.read_csv(processed / filename, low_memory=False)
            self.group_frames[name] = frame
            unknown = set(frame["work_id"].astype(str)) - self.work_ids
            if unknown:
                raise RuntimeError(f"{filename} contains unknown work IDs")
            self.groups[name] = {
                str(work_id): _records(group)
                for work_id, group in frame.groupby("work_id", sort=False)
            }

        self.queue = pd.read_csv(processed / "review_priority_queue.csv", low_memory=False)
        self.fund_progress = {
            str(row["work_id"]): json_safe(row)
            for row in pd.read_csv(
                processed / "fund_progress_evidence.csv", low_memory=False
            ).to_dict(orient="records")
        }
        candidates = pd.read_csv(processed / "duplicate_candidates.csv", low_memory=False)
        candidates = candidates.loc[
            candidates["review_candidate"].astype(str).str.casefold().eq("true")
        ]
        self.duplicate_pairs: dict[str, list[dict[str, Any]]] = {}
        for item in _records(candidates):
            for work_id in (str(item["work_id_a"]), str(item["work_id_b"])):
                self.duplicate_pairs.setdefault(work_id, []).append(item)

        self.trend_timeseries = pd.read_csv(processed / "trend_timeseries.csv")
        self.trend_alerts = pd.read_csv(processed / "trend_alerts.csv")
        self.hotspots = pd.read_csv(processed / "detector_hotspots.csv")
        self.authority_summary = pd.read_csv(
            processed / "review_priority_authority_summary.csv"
        )

        self.policy = self._json(processed / "risk_fusion_policy.json")
        self.guideline_manifest = self._json(processed / "guideline_manifest.json")
        self.guideline_chunks = self._json(processed / "guideline_chunks.json")
        self.day8_summary = self._json(processed / "day8_rag_summary.json")
        if not self.policy.get("policy_version"):
            raise RuntimeError("Risk-fusion policy version is missing")
        if not self.guideline_manifest.get("sha256"):
            raise RuntimeError("Guideline hash is missing")

        self.explanations: dict[str, dict[str, Any]] = {}
        with (processed / "explanation_context.jsonl").open(
            encoding="utf-8"
        ) as stream:
            for line in stream:
                item = json.loads(line)
                self.explanations[str(item["work_id"])] = item
        if set(self.explanations) != self.work_ids:
            raise RuntimeError("Explanation context must cover the same 3,000 works")

        self.work_master = self._index_demo("03_works.csv", "work_id")
        self.mp_master = self._index_demo("01_mp_master.csv", "mp_id")
        self.entity_master = self._index_demo("02_agencies_vendors.csv", "entity_id")

    @staticmethod
    def _json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _index_demo(self, filename: str, key: str) -> dict[str, dict[str, Any]]:
        frame = pd.read_csv(self.paths.demo_data_dir / filename, low_memory=False)
        if not frame[key].is_unique:
            raise RuntimeError(f"Read-only reference {filename} has duplicate {key}")
        return {
            str(row[key]): json_safe(row) for row in frame.to_dict(orient="records")
        }

    def get(self, name: str, work_id: str) -> dict[str, Any] | None:
        return self.single[name].get(work_id)

    def group(self, name: str, work_id: str) -> list[dict[str, Any]]:
        return self.groups[name].get(work_id, [])

    def require_work(self, work_id: str) -> None:
        if work_id not in self.work_ids:
            raise KeyError(work_id)

    def profile_frame(self) -> pd.DataFrame:
        return self.frames["features"]
