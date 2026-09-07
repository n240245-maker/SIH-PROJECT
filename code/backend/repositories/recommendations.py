"""Thread-safe runtime recommendation, event, and attachment storage."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_MEDIA = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
ALLOWED_DOCUMENT_TYPES = {
    "ESTIMATE", "SUPPORTING_DOCUMENT", "SANCTION_ORDER", "PROGRESS_PHOTO",
    "SITE_PHOTO", "COMPLETION_PHOTO", "UTILIZATION_CERTIFICATE", "HANDOVER_DOCUMENT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _image_gps(content: bytes) -> tuple[float | None, float | None]:
    """Read EXIF GPS when Pillow is available; missing metadata remains missing."""

    try:
        from PIL import ExifTags, Image

        with Image.open(io.BytesIO(content)) as image:
            exif = image.getexif()
            gps_info = exif.get_ifd(ExifTags.IFD.GPSInfo) if exif else {}
        latitude_values = gps_info.get(2)
        longitude_values = gps_info.get(4)
        if not latitude_values or not longitude_values:
            return None, None

        def decimal(values: Any, reference: str) -> float:
            degrees, minutes, seconds = (float(value) for value in values)
            result = degrees + minutes / 60 + seconds / 3600
            return -result if reference in {"S", "W"} else result

        return decimal(latitude_values, str(gps_info.get(1, "N"))), decimal(
            longitude_values, str(gps_info.get(3, "E"))
        )
    except Exception:
        return None, None


class RecommendationRepository:
    """Simple CSV-first-compatible runtime persistence outside frozen artifacts."""

    def __init__(self, runtime_dir: Path, *, max_upload_bytes: int = 10_000_000) -> None:
        self.root = runtime_dir.resolve()
        self.recommendations_path = self.root / "recommendations.json"
        self.events_path = self.root / "recommendation_events.jsonl"
        self.uploads_root = (self.root / "uploads").resolve()
        if self.root not in self.uploads_root.parents:
            raise ValueError("Upload storage must remain inside the runtime directory")
        self.max_upload_bytes = max_upload_bytes
        self._lock = threading.RLock()

    def _read_all_unlocked(self) -> list[dict[str, Any]]:
        if not self.recommendations_path.is_file():
            return []
        loaded = json.loads(self.recommendations_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise RuntimeError("Runtime recommendation store must contain a JSON list")
        return loaded

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_all_unlocked()

    def count(self) -> int:
        return len(self.list_all())

    def require(self, recommendation_id: str) -> dict[str, Any]:
        item = next(
            (row for row in self.list_all() if row.get("recommendation_id") == recommendation_id),
            None,
        )
        if item is None:
            raise KeyError(recommendation_id)
        return item

    def _write_all_unlocked(self, rows: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".recommendations-{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.recommendations_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _append_event_unlocked(
        self,
        recommendation_id: str,
        *,
        actor_role: str,
        actor_label: str,
        event_type: str,
        detail: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "event_id": f"EVT-{uuid.uuid4()}",
            "record_id": recommendation_id,
            "actor_role": actor_role,
            "actor_label": actor_label,
            "event_type": event_type,
            "timestamp": timestamp or _now(),
            "detail": detail[:500],
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
        return event

    def create(self, payload: dict[str, Any], *, mp_id: str, mp_name: str) -> dict[str, Any]:
        with self._lock:
            rows = self._read_all_unlocked()
            numbers = [
                int(str(row.get("recommendation_id", "")).removeprefix("REC-"))
                for row in rows
                if str(row.get("recommendation_id", "")).removeprefix("REC-").isdigit()
            ]
            recommendation_id = f"REC-{max(numbers, default=0) + 1:06d}"
            timestamp = _now()
            record = {
                "recommendation_id": recommendation_id,
                "status": "DRAFT",
                "mp_id": mp_id,
                "mp_name": mp_name,
                **payload,
                "precheck": None,
                "documents": [],
                "payments": [],
                "progress_updates": [],
                "runtime_checks": [],
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            rows.append(record)
            self._write_all_unlocked(rows)
            self._append_event_unlocked(
                recommendation_id,
                actor_role="MP",
                actor_label=mp_name,
                event_type="RECOMMENDATION_CREATED",
                detail=f"{payload['title']} saved as a draft recommendation",
                timestamp=timestamp,
            )
            return record

    def update(
        self,
        recommendation_id: str,
        changes: dict[str, Any],
        *,
        actor_role: str,
        actor_label: str,
        event_type: str,
        detail: str,
    ) -> dict[str, Any]:
        with self._lock:
            rows = self._read_all_unlocked()
            index = next(
                (position for position, row in enumerate(rows) if row.get("recommendation_id") == recommendation_id),
                None,
            )
            if index is None:
                raise KeyError(recommendation_id)
            rows[index] = {**rows[index], **changes, "updated_at": _now()}
            self._write_all_unlocked(rows)
            self._append_event_unlocked(
                recommendation_id,
                actor_role=actor_role,
                actor_label=actor_label,
                event_type=event_type,
                detail=detail,
            )
            return rows[index]

    def events(self, recommendation_id: str) -> list[dict[str, Any]]:
        if not self.events_path.is_file():
            return []
        result: list[dict[str, Any]] = []
        with self.events_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    if row.get("record_id") == recommendation_id:
                        result.append(row)
        return result

    def store_document(
        self,
        recommendation_id: str,
        payload: dict[str, Any],
        *,
        actor_role: str,
        actor_label: str,
    ) -> dict[str, Any]:
        document_type = str(payload["document_type"]).upper().replace(" ", "_")
        if document_type not in ALLOWED_DOCUMENT_TYPES:
            raise ValueError("Unsupported document type")
        media_type = str(payload["media_type"]).casefold()
        extension = ALLOWED_MEDIA.get(media_type)
        if extension is None:
            raise ValueError("Only PDF, JPG, JPEG, and PNG files are allowed")
        original_name = Path(str(payload["original_filename"])).name
        if original_name != str(payload["original_filename"]) or Path(original_name).suffix.casefold() not in {
            ".pdf", ".jpg", ".jpeg", ".png"
        }:
            raise ValueError("The uploaded filename is not allowed")
        try:
            content = base64.b64decode(str(payload["content_base64"]), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("The uploaded file is not valid base64") from exc
        if not content or len(content) > self.max_upload_bytes:
            raise ValueError("The uploaded file must be non-empty and no larger than 10 MB")
        if media_type == "application/pdf" and not content.startswith(b"%PDF"):
            raise ValueError("The file content does not match a PDF")
        if media_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("The file content does not match a PNG image")
        if media_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
            raise ValueError("The file content does not match a JPEG image")

        with self._lock:
            record = self.require(recommendation_id)
            self.uploads_root.mkdir(parents=True, exist_ok=True)
            document_id = f"DOC-{uuid.uuid4()}"
            stored_name = f"{uuid.uuid4().hex}{extension}"
            destination = (self.uploads_root / stored_name).resolve()
            if self.uploads_root not in destination.parents:
                raise RuntimeError("Unsafe upload destination")
            with destination.open("xb") as stream:
                stream.write(content)
            exif_latitude, exif_longitude = _image_gps(content) if media_type.startswith("image/") else (None, None)
            supplied_latitude = payload.get("latitude")
            supplied_longitude = payload.get("longitude")
            metadata = {
                "document_id": document_id,
                "document_type": document_type,
                "original_filename": original_name,
                "media_type": media_type,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "stored_object_id": stored_name,
                "uploaded_at": _now(),
                "photo_latitude": exif_latitude if exif_latitude is not None else supplied_latitude,
                "photo_longitude": exif_longitude if exif_longitude is not None else supplied_longitude,
                "coordinate_source": "EXIF" if exif_latitude is not None else "USER_SUPPLIED" if supplied_latitude is not None else "UNAVAILABLE",
                "authenticity_note": "Location metadata does not establish image authenticity.",
            }
            documents = [*record.get("documents", []), metadata]
            return self.update(
                recommendation_id,
                {"documents": documents},
                actor_role=actor_role,
                actor_label=actor_label,
                event_type="PHOTO_UPLOADED" if media_type.startswith("image/") else "DOCUMENT_UPLOADED",
                detail=f"{document_type.replace('_', ' ').title()} uploaded",
            )
