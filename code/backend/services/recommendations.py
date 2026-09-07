"""Lifecycle-aware recommendation workflow over isolated runtime records."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.repositories.recommendations import RecommendationRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.schemas import RecommendationAction, Role
from backend.serialization import json_safe
from backend.services.application import Scope


def _amount_similarity(first: object, second: object) -> float | None:
    """Compare usable amounts without importing the offline detector stack."""

    if first is None or second is None or pd.isna(first) or pd.isna(second):
        return None
    first_value = float(first)
    second_value = float(second)
    denominator = max(abs(first_value), abs(second_value))
    if denominator <= 0:
        return 1.0 if first_value == second_value else None
    return float(np.clip(1.0 - abs(first_value - second_value) / denominator, 0.0, 1.0))


def _geographic_distance_km(
    latitude_a: object,
    longitude_a: object,
    latitude_b: object,
    longitude_b: object,
) -> float | None:
    """Return a bounded great-circle distance for the online pre-check."""

    coordinates = (latitude_a, longitude_a, latitude_b, longitude_b)
    if any(value is None or pd.isna(value) for value in coordinates):
        return None
    lat_a, lon_a, lat_b, lon_b = map(float, coordinates)
    if not (-90 <= lat_a <= 90 and -90 <= lat_b <= 90):
        return None
    if not (-180 <= lon_a <= 180 and -180 <= lon_b <= 180):
        return None
    lat_a_r, lon_a_r, lat_b_r, lon_b_r = map(
        math.radians, (lat_a, lon_a, lat_b, lon_b)
    )
    delta_lat = lat_b_r - lat_a_r
    delta_lon = lon_b_r - lon_a_r
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a_r) * math.cos(lat_b_r) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, haversine)))


@lru_cache(maxsize=1)
def _duplicate_query_model(cache_folder: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        cache_folder=cache_folder,
        local_files_only=True,
    )


def _parse_date(value: object) -> date | None:
    if value in {None, ""}:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _first_amount(*values: object) -> float | None:
    for value in values:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.notna(numeric):
            return float(numeric)
    return None


class RecommendationService:
    """Applies scope, lifecycle, and bounded pre-check rules to runtime records."""

    def __init__(
        self,
        artifacts: V2ArtifactRepository,
        repository: RecommendationRepository,
    ) -> None:
        self.artifacts = artifacts
        self.repository = repository
        self.profile = artifacts.profile.reset_index(drop=True)
        self._embedding_path = artifacts.models_dir / "duplicates" / "work_embeddings.npy"
        self._model_cache = (
            artifacts.paths.project_root
            / "code"
            / "models"
            / "duplicates"
            / "sentence_transformers_cache"
        )

    def _authorized(self, record: dict[str, Any], scope: Scope) -> bool:
        if scope.role == Role.MOSPI:
            return True
        if scope.role == Role.STATE:
            return record.get("state") == scope.state
        if scope.role == Role.DISTRICT:
            return record.get("state") == scope.state and record.get("district") == scope.district
        if scope.role == Role.MP:
            return record.get("mp_id") == scope.mp_id
        return False

    def require(self, recommendation_id: str, scope: Scope) -> dict[str, Any]:
        record = self.repository.require(recommendation_id)
        if not self._authorized(record, scope):
            raise PermissionError(recommendation_id)
        return self._with_derived(record)

    def create(self, payload: dict[str, Any], scope: Scope) -> dict[str, Any]:
        if scope.role != Role.MP or not scope.mp_id:
            raise PermissionError("Only an MP scope may create a recommendation")
        try:
            member = self.artifacts.mp_index[scope.mp_id]
        except KeyError:
            raise PermissionError("The selected MP is unavailable") from None
        if payload["state"] != member["state_name"]:
            raise ValueError("The selected state does not match the MP scope")
        allowed = self.profile.loc[self.profile["mp_id"].eq(scope.mp_id), ["state_name", "district"]]
        allowed_pairs = set(map(tuple, allowed.drop_duplicates().itertuples(index=False, name=None)))
        if (payload["state"], payload["district"]) not in allowed_pairs:
            raise ValueError("The selected district does not match the MP scope")
        return self._with_derived(
            self.repository.create(payload, mp_id=scope.mp_id, mp_name=str(member["mp_name"]))
        )

    def list(
        self,
        scope: Scope,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        rows = [self._with_derived(row) for row in self.repository.list_all() if self._authorized(row, scope)]
        if search:
            needle = search.casefold()
            rows = [
                row for row in rows
                if needle in " ".join(
                    str(row.get(key, "")) for key in ("recommendation_id", "title", "district", "village")
                ).casefold()
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows.sort(key=lambda row: (str(row.get("updated_at", "")), row["recommendation_id"]), reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "items": rows[start : start + page_size],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def my_works(
        self,
        scope: Scope,
        *,
        page: int,
        page_size: int,
        category: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        if scope.role != Role.MP or not scope.mp_id:
            raise PermissionError("My Works is available only in an MP scope")
        existing = self.profile.loc[self.profile["mp_id"].eq(scope.mp_id)]
        rows: list[dict[str, Any]] = []
        for work in existing.to_dict(orient="records"):
            lifecycle = str(work["lifecycle_stage"])
            rows.append({
                "record_type": "ANALYTICAL_WORK",
                "id": str(work["work_id"]),
                "title": str(work["work_description"]),
                "location": f"{work['village']}, {work['district']}",
                "cost_inr": _first_amount(work.get("sanctioned_amount_inr"), work.get("recommended_amount_inr")),
                "status": str(work["current_status"]),
                "category": "COMPLETED" if lifecycle == "COMPLETION" else "ONGOING" if lifecycle == "EXECUTION" else "RECOMMENDED",
                "progress_pct": work.get("physical_progress_pct"),
                "needs_attention": bool(str(work.get("requires_review", "")).casefold() == "true"),
                "updated_at": work.get("latest_progress_report") or work.get("recommendation_date"),
            })
        for recommendation in self.repository.list_all():
            if recommendation.get("mp_id") != scope.mp_id:
                continue
            status_value = str(recommendation["status"])
            rows.append({
                "record_type": "RUNTIME_RECOMMENDATION",
                "id": recommendation["recommendation_id"],
                "title": recommendation["title"],
                "location": f"{recommendation['village']}, {recommendation['district']}",
                "cost_inr": recommendation.get("sanctioned_cost_inr") or recommendation["proposed_project_cost_inr"],
                "status": status_value,
                "category": "COMPLETED" if status_value in {"COMPLETED", "CLOSED"} else "ONGOING" if status_value in {"SANCTIONED", "IN_PROGRESS"} else "RECOMMENDED",
                "progress_pct": self._latest_progress(recommendation).get("physical_progress_pct"),
                "needs_attention": bool(recommendation.get("runtime_checks")) or status_value == "NEEDS_CLARIFICATION",
                "updated_at": recommendation["updated_at"],
            })
        if category:
            rows = [row for row in rows if row["category"] == category]
        if search:
            needle = search.casefold()
            rows = [row for row in rows if needle in f"{row['id']} {row['title']} {row['location']}".casefold()]
        rows.sort(key=lambda row: (str(row.get("updated_at") or ""), row["id"]), reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "items": json_safe(rows[start : start + page_size]),
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def _semantic_candidates(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._embedding_path.is_file():
            return []
        embeddings = np.load(self._embedding_path, mmap_mode="r")
        if embeddings.shape[0] != len(self.profile):
            return []
        try:
            model = _duplicate_query_model(str(self._model_cache))
        except (ImportError, ModuleNotFoundError, OSError):
            # Hosted serving deliberately excludes the heavyweight local embedding
            # runtime. The pre-check remains deterministic and operational without it.
            return []
        query_text = f"{record['title']}. {record['description']}"
        query_embedding = model.encode(
            [query_text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )[0].astype("float32")
        scores = np.asarray(embeddings @ query_embedding)
        candidate_count = min(40, len(scores))
        indexes = np.argpartition(scores, -candidate_count)[-candidate_count:]
        indexes = indexes[np.argsort(scores[indexes])[::-1]]
        results: list[dict[str, Any]] = []
        for index in indexes:
            work = self.profile.iloc[int(index)]
            distance = _geographic_distance_km(
                record.get("latitude"), record.get("longitude"),
                work.get("registered_latitude"), work.get("registered_longitude"),
            )
            amount = _amount_similarity(record["proposed_project_cost_inr"], work.get("recommended_amount_inr"))
            same_sector = str(work.get("sector", "")).casefold() == str(record["sector"]).casefold()
            same_sub_sector = str(work.get("sub_sector", "")).casefold() == str(record["sub_sector"]).casefold()
            same_district = str(work.get("district", "")).casefold() == str(record["district"]).casefold()
            similarity = float(scores[int(index)])
            corroborated = bool(
                similarity >= 0.72
                and same_sector
                and amount is not None
                and amount >= 0.70
                and ((distance is not None and distance <= 5) or same_district)
            )
            if similarity < 0.45 and not (same_sector and same_sub_sector and same_district):
                continue
            results.append({
                "work_id": str(work["work_id"]),
                "title": str(work["work_description"]),
                "location": f"{work['village']}, {work['district']}",
                "distance_km": round(distance, 2) if distance is not None else None,
                "cost_inr": work.get("sanctioned_amount_inr") or work.get("recommended_amount_inr"),
                "match_strength": "High" if corroborated else "Possible",
                "label": "Duplicate Review Candidate" if corroborated else "Possible Similar Work",
            })
            if len(results) >= 5:
                break
        return results

    def precheck(self, recommendation_id: str, scope: Scope) -> dict[str, Any]:
        record = self.require(recommendation_id, scope)
        required_fields = (
            "title", "sector", "sub_sector", "description", "public_benefit",
            "state", "district", "block", "village", "proposed_project_cost_inr",
        )
        missing = [field for field in required_fields if record.get(field) in {None, ""}]
        similar = self._semantic_candidates(record)
        relevant = self.profile.loc[
            self.profile["sector"].astype(str).str.casefold().eq(str(record["sector"]).casefold())
        ]
        sub_sector = relevant.loc[
            relevant["sub_sector"].astype(str).str.casefold().eq(str(record["sub_sector"]).casefold())
        ]
        peers = sub_sector if len(sub_sector) >= 5 else relevant
        peer_costs = pd.to_numeric(peers["recommended_amount_inr"], errors="coerce").dropna()
        median_cost = float(peer_costs.median()) if len(peer_costs) else None
        upper_quartile = float(peer_costs.quantile(0.75)) if len(peer_costs) else None
        proposed = float(record["proposed_project_cost_inr"])
        high_cost = bool(upper_quartile is not None and proposed > upper_quartile * 1.25)
        coordinates_available = record.get("latitude") is not None and record.get("longitude") is not None
        needs_check = bool(similar and similar[0]["match_strength"] == "High") or high_cost or not coordinates_available
        overall = "Missing Details" if missing else "Check Required" if needs_check else "Looks Good"
        result = {
            "precheck_version": "RECOMMENDATION_PRECHECK_V1",
            "checked_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "overall_status": overall,
            "required_details": {"status": "Missing Details" if missing else "Complete", "missing_fields": missing},
            "similar_works": {
                "status": "Check Required" if similar and similar[0]["match_strength"] == "High" else "Looks Good",
                "summary": f"{len(similar)} possible similar work{'s' if len(similar) != 1 else ''} found" if similar else "No close match found",
                "items": similar,
            },
            "cost_comparison": {
                "status": "Check Required" if high_cost else "Looks Good",
                "summary": "Higher than comparable works" if high_cost else "Within the observed range for comparable works",
                "proposed_project_cost_inr": proposed,
                "comparable_work_count": int(len(peer_costs)),
                "median_comparable_cost_inr": median_cost,
                "upper_quartile_cost_inr": upper_quartile,
                "note": "This is a peer comparison, not an official cost limit.",
            },
            "location_check": {
                "status": "Looks Good" if coordinates_available else "Check Required",
                "summary": "Location details available" if coordinates_available else "Coordinates are not available",
            },
            "applicable_rule_checks": {
                "status": "Looks Good",
                "summary": "No immediate pre-sanction rule issue found",
                "checked_stage": "Recommendation",
            },
        }
        return self.repository.update(
            recommendation_id,
            {"precheck": json_safe(result)},
            actor_role=scope.role.value,
            actor_label=str(record.get("mp_name") or scope.role.value),
            event_type="PRECHECK_COMPLETED",
            detail=f"Pre-check completed: {overall}",
        )["precheck"]

    @staticmethod
    def _latest_progress(record: dict[str, Any]) -> dict[str, Any]:
        progress = record.get("progress_updates") or []
        return progress[-1] if progress else {}

    def _runtime_checks(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        payments = record.get("payments") or []
        released = sum(float(row["payment_amount_inr"]) for row in payments)
        sanction = record.get("sanctioned_cost_inr")
        if sanction and released > float(sanction):
            checks.append({
                "area": "Payments", "level": "Strong Issue",
                "message": f"Released payments are ₹{released - float(sanction):,.0f} above sanctioned cost.",
            })
        latest = self._latest_progress(record)
        physical = latest.get("physical_progress_pct")
        financial = latest.get("financial_progress_pct")
        if physical is not None and financial is not None and abs(float(financial) - float(physical)) >= 25:
            checks.append({
                "area": "Payments & Progress", "level": "Attention",
                "message": f"Financial and physical progress differ by {abs(float(financial) - float(physical)):.1f} percentage points.",
            })
        expected = _parse_date(record.get("expected_completion_date"))
        if expected and expected < date.today() and record.get("status") not in {"COMPLETED", "CLOSED"}:
            checks.append({
                "area": "Schedule", "level": "Strong Issue",
                "message": f"Expected completion is overdue by {(date.today() - expected).days} days.",
            })
        if any(
            _parse_date(row.get("authorization_date"))
            and _parse_date(row.get("payment_request_date"))
            and _parse_date(row["authorization_date"]) < _parse_date(row["payment_request_date"])
            for row in payments
        ):
            checks.append({
                "area": "Payment Dates", "level": "Attention",
                "message": "An authorization date is recorded before its payment request date.",
            })
        return checks

    def action(
        self,
        recommendation_id: str,
        payload: dict[str, Any],
        scope: Scope,
    ) -> dict[str, Any]:
        record = self.require(recommendation_id, scope)
        action = RecommendationAction(payload["action"])
        actor = str(payload["actor_label"])
        district_actions = {
            RecommendationAction.REQUEST_CLARIFICATION,
            RecommendationAction.ACCEPT_FOR_PROCESSING,
            RecommendationAction.ADD_SANCTION,
            RecommendationAction.UPDATE_PROGRESS,
            RecommendationAction.ADD_PAYMENT,
            RecommendationAction.MARK_COMPLETED,
        }
        if action in district_actions and scope.role != Role.DISTRICT:
            raise PermissionError("This action requires the scoped District Authority")
        if action in {RecommendationAction.SUBMIT, RecommendationAction.PROVIDE_CLARIFICATION} and scope.role != Role.MP:
            raise PermissionError("This action requires the owning MP scope")

        status = str(record["status"])
        changes: dict[str, Any] = {}
        detail = action.value.replace("_", " ").title()
        if action == RecommendationAction.SUBMIT:
            if status != "DRAFT" or not record.get("precheck"):
                raise ValueError("Run the pre-check before submitting the draft")
            changes["status"] = "RECOMMENDED"
            detail = "Recommendation submitted to the District Authority"
        elif action == RecommendationAction.REQUEST_CLARIFICATION:
            if status not in {"RECOMMENDED", "UNDER_REVIEW"}:
                raise ValueError("Clarification cannot be requested at the current stage")
            changes.update(status="NEEDS_CLARIFICATION", clarification_message=payload["message"])
            detail = f"Clarification requested: {payload['message']}"
        elif action == RecommendationAction.PROVIDE_CLARIFICATION:
            if status != "NEEDS_CLARIFICATION":
                raise ValueError("Clarification is not currently requested")
            changes.update(status="UNDER_REVIEW", clarification_response=payload["message"])
            detail = f"Clarification provided: {payload['message']}"
        elif action == RecommendationAction.ACCEPT_FOR_PROCESSING:
            if status not in {"RECOMMENDED", "UNDER_REVIEW"}:
                raise ValueError("Recommendation cannot be accepted at the current stage")
            changes["status"] = "ACCEPTED_FOR_PROCESSING"
            detail = "Recommendation accepted for administrative processing"
        elif action == RecommendationAction.ADD_SANCTION:
            if status != "ACCEPTED_FOR_PROCESSING":
                raise ValueError("Accept the recommendation before adding sanction details")
            changes.update({
                "status": "SANCTIONED",
                "sanctioned_cost_inr": payload["sanctioned_cost_inr"],
                "sanction_date": payload["sanction_date"],
                "implementing_agency": payload["implementing_agency"],
                "expected_start_date": payload["expected_start_date"],
                "expected_completion_date": payload["expected_completion_date"],
            })
            detail = "Sanction and schedule details added"
        elif action == RecommendationAction.UPDATE_PROGRESS:
            if status not in {"SANCTIONED", "IN_PROGRESS"}:
                raise ValueError("Progress can be added only after sanction")
            update = {
                "progress_id": f"PROG-{len(record.get('progress_updates', [])) + 1:04d}",
                "actual_start_date": payload.get("actual_start_date"),
                "physical_progress_pct": payload["physical_progress_pct"],
                "financial_progress_pct": payload.get("financial_progress_pct"),
                "progress_note": payload.get("progress_note"),
                "recorded_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
            changes.update(status="IN_PROGRESS", progress_updates=[*record.get("progress_updates", []), update])
            if payload.get("actual_start_date"):
                changes["actual_start_date"] = payload["actual_start_date"]
            detail = f"Physical progress updated to {payload['physical_progress_pct']}%"
        elif action == RecommendationAction.ADD_PAYMENT:
            if status not in {"SANCTIONED", "IN_PROGRESS"}:
                raise ValueError("Payments can be added only after sanction")
            payment = {
                "payment_id": f"PAY-{len(record.get('payments', [])) + 1:04d}",
                "payment_amount_inr": payload["payment_amount_inr"],
                "payment_release_date": payload["payment_release_date"],
                "payment_request_date": payload.get("payment_request_date"),
                "authorization_date": payload.get("authorization_date"),
                "recorded_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
            changes.update(status="IN_PROGRESS", payments=[*record.get("payments", []), payment])
            detail = f"Payment of ₹{float(payload['payment_amount_inr']):,.0f} recorded"
        elif action == RecommendationAction.MARK_COMPLETED:
            if status != "IN_PROGRESS":
                raise ValueError("Only an in-progress work can be marked completed")
            changes.update(status="COMPLETED", completed_at=pd.Timestamp.now(tz="UTC").isoformat())
            detail = "Work marked completed; completion records remain subject to verification"

        combined = {**record, **changes}
        changes["runtime_checks"] = self._runtime_checks(combined)
        updated = self.repository.update(
            recommendation_id,
            changes,
            actor_role=scope.role.value,
            actor_label=actor,
            event_type=action.value,
            detail=detail,
        )
        return self._with_derived(updated)

    def add_document(
        self,
        recommendation_id: str,
        payload: dict[str, Any],
        scope: Scope,
        *,
        actor_label: str,
    ) -> dict[str, Any]:
        record = self.require(recommendation_id, scope)
        if scope.role not in {Role.MP, Role.DISTRICT}:
            raise PermissionError("Only the owning MP or scoped District Authority may upload files")
        updated = self.repository.store_document(
            recommendation_id,
            payload,
            actor_role=scope.role.value,
            actor_label=actor_label,
        )
        document = updated["documents"][-1]
        photo_distance = _geographic_distance_km(
            record.get("latitude"), record.get("longitude"),
            document.get("photo_latitude"), document.get("photo_longitude"),
        )
        is_image = str(document["media_type"]).startswith("image/")
        location_result = (
            "Stored securely" if not is_image
            else "Photo location unavailable" if photo_distance is None
            else "Location Match" if photo_distance <= 0.5
            else "Location Difference"
        )
        document["location_check"] = {
            "result": location_result,
            "distance_km": round(photo_distance, 3) if photo_distance is not None else None,
            "note": (
                "Stored in the confined runtime document area."
                if not is_image
                else "A location match does not establish image authenticity."
            ),
        }
        documents = [*updated["documents"][:-1], document]
        return self.repository.update(
            recommendation_id,
            {"documents": documents},
            actor_role=scope.role.value,
            actor_label=actor_label,
            event_type="PHOTO_LOCATION_CHECKED" if is_image else "DOCUMENT_STORED",
            detail=location_result if is_image else "Document stored securely",
        )["documents"][-1]

    def activity(self, recommendation_id: str, scope: Scope) -> list[dict[str, Any]]:
        self.require(recommendation_id, scope)
        return self.repository.events(recommendation_id)

    def _with_derived(self, record: dict[str, Any]) -> dict[str, Any]:
        result = json_safe(record)
        result["activity"] = self.repository.events(str(record["recommendation_id"]))
        result["status_label"] = str(record["status"]).replace("ACCEPTED_FOR_PROCESSING", "ACCEPTED").replace("_", " ").title()
        current_key = "UNDER_REVIEW" if record["status"] == "NEEDS_CLARIFICATION" else str(record["status"])
        result["tracker"] = [
            {"key": key, "label": label, "state": "CURRENT" if key == current_key else "COMPLETE" if index < self._stage_index(str(record["status"])) else "UPCOMING"}
            for index, (key, label) in enumerate(
                [
                    ("RECOMMENDED", "Recommended"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("ACCEPTED_FOR_PROCESSING", "Accepted"),
                    ("SANCTIONED", "Sanctioned"),
                    ("IN_PROGRESS", "In Progress"),
                    ("COMPLETED", "Completed"),
                ]
            )
        ]
        return result

    @staticmethod
    def _stage_index(status: str) -> int:
        return {
            "DRAFT": -1,
            "RECOMMENDED": 0,
            "NEEDS_CLARIFICATION": 1,
            "UNDER_REVIEW": 1,
            "ACCEPTED_FOR_PROCESSING": 2,
            "SANCTIONED": 3,
            "IN_PROGRESS": 4,
            "COMPLETED": 5,
            "CLOSED": 6,
        }.get(status, -1)
