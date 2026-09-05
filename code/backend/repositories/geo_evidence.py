"""Append-only local prototype storage for live/uploaded geo evidence."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GeoEvidenceRepository:
    def __init__(self, runtime_dir: Path, *, max_image_bytes: int = 5_000_000) -> None:
        self.root = (runtime_dir / "site-evidence").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.submissions_path = self.root / "submissions.jsonl"
        self.verifications_path = self.root / "verifications.jsonl"
        self.max_image_bytes = max_image_bytes
        self._lock = threading.Lock()

    @staticmethod
    def _rows(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _append(path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")

    def list_for_work(self, work_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self._rows(self.submissions_path) if row["work_id"] == work_id]
        latest_verification: dict[str, dict[str, Any]] = {}
        for row in self._rows(self.verifications_path):
            latest_verification[row["evidence_id"]] = row
        for row in rows:
            row["district_verification"] = latest_verification.get(row["evidence_id"])
        return rows

    def create(self, work_id: str, payload: dict[str, Any], *, agency_id: str) -> dict[str, Any]:
        try:
            image = base64.b64decode(payload.pop("image_base64"), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Image payload is not valid base64") from exc
        if not image or len(image) > self.max_image_bytes:
            raise ValueError("Image must be non-empty and within the configured size limit")
        media_type = str(payload["image_media_type"])
        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[media_type]
        evidence_id = f"GEO-LIVE-{uuid.uuid4()}"
        image_path = (self.root / f"{evidence_id}{extension}").resolve()
        if self.root not in image_path.parents:
            raise RuntimeError("Unsafe runtime image path")
        created_at = datetime.now(timezone.utc).isoformat()
        row = {
            "evidence_id": evidence_id, "work_id": work_id, **payload,
            "implementing_agency_id": agency_id, "image_sha256": hashlib.sha256(image).hexdigest(),
            "image_path_or_object_id": image_path.name, "stored_at": created_at,
            "verification_status": "PENDING_DISTRICT_VERIFICATION",
            "provenance_note": (
                "Image hash proves stored-file integrity, not authenticity. Uploaded images and live captures have distinct provenance."
            ),
        }
        with self._lock:
            with image_path.open("xb") as stream:
                stream.write(image)
            self._append(self.submissions_path, row)
        return row

    def verify(self, evidence_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        submissions = {row["evidence_id"]: row for row in self._rows(self.submissions_path)}
        if evidence_id not in submissions:
            raise KeyError(evidence_id)
        row = {
            "verification_id": f"GEO-VERIFY-{uuid.uuid4()}", "evidence_id": evidence_id,
            **payload, "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._append(self.verifications_path, row)
        return row

    def image(self, evidence_id: str) -> tuple[bytes, str]:
        row = next((item for item in self._rows(self.submissions_path) if item["evidence_id"] == evidence_id), None)
        if row is None:
            raise KeyError(evidence_id)
        path = (self.root / str(row["image_path_or_object_id"])).resolve()
        if self.root not in path.parents or not path.is_file():
            raise KeyError(evidence_id)
        return path.read_bytes(), str(row["image_media_type"])
