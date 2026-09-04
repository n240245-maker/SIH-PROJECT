"""Thread-safe append-only officer review and audit repository."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReviewRepository:
    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.reviews_path = runtime_dir / "reviews.jsonl"
        self.audit_path = runtime_dir / "audit_log.jsonl"
        self._lock = threading.Lock()

    def list_for_work(self, work_id: str) -> list[dict[str, Any]]:
        if not self.reviews_path.exists():
            return []
        result: list[dict[str, Any]] = []
        with self.reviews_path.open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                if item.get("work_id") == work_id:
                    result.append(item)
        return result

    def latest_statuses(self) -> dict[str, str]:
        latest: dict[str, str] = {}
        if not self.reviews_path.exists():
            return latest
        with self.reviews_path.open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                latest[str(item["work_id"])] = str(item["status"])
        return latest

    def append(self, work_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        review = {
            "review_id": str(uuid.uuid4()), "work_id": work_id,
            **payload, "created_at": now,
        }
        audit = {
            "audit_id": str(uuid.uuid4()), "event_type": "REVIEW_STATUS_RECORDED",
            "work_id": work_id, "review_id": review["review_id"],
            "actor_role": review["actor_role"], "actor_label": review["actor_label"],
            "status": review["status"], "created_at": now,
        }
        with self._lock:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            with self.reviews_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(review, ensure_ascii=False) + "\n")
            with self.audit_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(audit, ensure_ascii=False) + "\n")
        return review

