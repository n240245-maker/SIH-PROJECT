"""Role scoping, dashboards, queues, work details, and trend views."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from backend.repositories import ApplicationArtifactRepository, ReviewRepository
from backend.schemas import Role
from backend.serialization import json_safe
from backend.presentation import (
    ALERT_ACTIONS,
    ALERT_LABELS,
    ATTENTION_LEVEL_LABELS,
    attention_level_from_band,
    alert_category,
    build_work_presentation,
    is_actionable_alert,
)


@dataclass(frozen=True, slots=True)
class Scope:
    role: Role = Role.MOSPI
    state: str | None = None
    district: str | None = None
    mp_id: str | None = None
    agency_id: str | None = None


class ApplicationService:
    def __init__(self, artifacts: ApplicationArtifactRepository, reviews: ReviewRepository) -> None:
        self.artifacts = artifacts
        self.reviews = reviews
        self.work_view = artifacts.frames["features"].merge(
            artifacts.frames["priority"],
            on=["work_id", "lifecycle_stage"], validate="one_to_one",
        )
        self._actionable_work_ids = {
            str(work_id)
            for work_id, alerts in artifacts.groups["alerts"].items()
            if any(is_actionable_alert(item.get("alert_type")) for item in alerts)
        }
        self.work_view["requires_review"] = self.work_view["work_id"].astype(str).isin(
            self._actionable_work_ids
        )
        self.work_view["attention_level"] = self.work_view.apply(
            lambda row: attention_level_from_band(
                row["review_priority_band"], bool(row["requires_review"])
            ),
            axis=1,
        )
        queue_ids = set(artifacts.queue["work_id"].astype(str))
        self.queue_view = self.work_view.loc[
            self.work_view["work_id"].astype(str).isin(queue_ids)
        ].copy()
        self._trend_details: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for (group_value, metric), group in artifacts.trend_alerts.groupby(
            ["group_value", "metric"], sort=False
        ):
            self._trend_details[(str(group_value), str(metric))] = json_safe(
                group.sort_values("month").to_dict(orient="records")
            )

    def _validate_scope(self, scope: Scope) -> None:
        if scope.role == Role.STATE and not scope.state:
            raise ValueError("STATE role requires state")
        if scope.role == Role.DISTRICT and (not scope.state or not scope.district):
            raise ValueError("DISTRICT role requires state and district")
        if scope.role == Role.MP and not scope.mp_id:
            raise ValueError("MP role requires mp_id")
        if scope.role == Role.IA and not scope.agency_id:
            raise ValueError("IA role requires agency_id")

    def scoped(self, frame: pd.DataFrame, scope: Scope) -> pd.DataFrame:
        self._validate_scope(scope)
        result = frame
        if scope.role in {Role.STATE, Role.DISTRICT}:
            result = result.loc[result["state_name"].eq(scope.state)]
        if scope.role == Role.DISTRICT:
            result = result.loc[result["district"].eq(scope.district)]
        if scope.role == Role.MP:
            result = result.loc[result["mp_id"].eq(scope.mp_id)]
        if scope.role == Role.IA:
            result = result.loc[result["implementing_agency_id"].eq(scope.agency_id)]
        return result

    def scope_options(self) -> dict[str, Any]:
        base = self.work_view
        districts = base[["state_name", "district"]].drop_duplicates().sort_values(["state_name", "district"])
        mps = []
        for mp_id in sorted(base["mp_id"].unique()):
            mp = self.artifacts.mp_master.get(str(mp_id), {})
            mps.append({"mp_id": str(mp_id), "mp_name": mp.get("mp_name", str(mp_id)),
                        "state_name": mp.get("state_name"), "constituency": mp.get("constituency")})
        agencies = [
            {"agency_id": str(entity_id), "agency_name": item.get("entity_name", str(entity_id)),
             "state_name": item.get("state_name"), "district": item.get("district")}
            for entity_id, item in sorted(self.artifacts.entity_master.items())
            if str(item.get("entity_type")) == "IMPLEMENTING_AGENCY"
        ]
        return {"roles": [Role.MOSPI.value, Role.STATE.value, Role.DISTRICT.value, Role.MP.value],
                "states": sorted(base["state_name"].dropna().unique().tolist()),
                "districts": json_safe(districts.to_dict(orient="records")), "mps": mps,
                "agencies": agencies}

    def authorize_work(self, work_id: str, scope: Scope) -> None:
        self.artifacts.require_work(work_id)
        allowed = self.scoped(self.work_view, scope)
        if work_id not in set(allowed["work_id"].astype(str)):
            raise KeyError(work_id)

    def overview(self, scope: Scope) -> dict[str, Any]:
        frame = self.scoped(self.work_view, scope)
        attention_counts = {
            code: int(frame["attention_level"].eq(code).sum())
            for code in ATTENTION_LEVEL_LABELS
        }
        attention_percentages = {
            code: round(count / len(frame) * 100, 2) if len(frame) else 0.0
            for code, count in attention_counts.items()
        }
        return json_safe({
            "scope": asdict(scope), "work_count": len(frame),
            "review_queue_count": int(frame["review_priority_band"].isin(["HIGH", "CRITICAL"]).sum()),
            "mean_review_priority": frame["review_priority_score_0_100"].mean(),
            "priority_bands": frame["review_priority_band"].value_counts().to_dict(),
            "attention_levels": attention_counts,
            "attention_level_percentages": attention_percentages,
            "attention_level_labels": ATTENTION_LEVEL_LABELS,
            "requires_review_count": int(frame["requires_review"].sum()),
            "immediate_priority_count": attention_counts["IMMEDIATE_PRIORITY"],
            "lifecycle_counts": frame["lifecycle_stage"].value_counts().to_dict(),
            "financial_snapshot": {
                "sanctioned_amount_inr": frame["sanctioned_amount_inr"].sum(),
                "released_amount_inr": frame["released_payment_total_inr_as_of"].sum(),
                "observed_over_sanction_count": int(frame["already_over_sanction_as_of"].sum()),
                "observed_overdue_count": int(frame["already_overdue_as_of"].sum())},
            "review_signals": {
                "duplicate_review_work_count": int(frame["has_duplicate_review_candidate"].sum()),
                "payment_evidence_work_count": int(frame["has_payment_evidence"].sum()),
                "compliance_review_work_count": int(frame["has_compliance_review"].sum())},
            "as_of_date": str(frame["feature_snapshot_date"].iloc[0]) if len(frame) else None,
            "language_note": "Review Priority is a deterministic triage score, not a probability or verdict.",
            "attention_level_note": (
                "Attention Level is a presentation aid derived from the frozen Review Priority "
                "and current actionable evidence. It does not change the underlying analytical score."
            ),
            "distribution_note": (
                "Distribution reflects the current frozen analytical snapshot. "
                "Categories were not artificially balanced."
            ),
            "natural_distribution_note": (
                "Distribution reflects the current frozen analytical snapshot. "
                "Categories were not artificially balanced."
            ),
        })

    @staticmethod
    def _as_bool(series: pd.Series) -> pd.Series:
        return series.astype(str).str.casefold().isin({"true", "1"})

    def review_queue(self, scope: Scope, *, page: int, page_size: int,
                     search: str | None, lifecycle: str | None, band: str | None,
                     attention_level: str | None, review_need: str | None,
                     sector: str | None, sub_sector: str | None, alert_type: str | None,
                     duplicate: bool | None, compliance: bool | None,
                     overdue: bool | None, over_sanction: bool | None,
                     review_status: str | None, sort_by: str, sort_order: str) -> dict[str, Any]:
        # Preserve the Day-9 default HIGH/CRITICAL queue for existing API clients.
        # The Day-9.2 UI explicitly requests review_need=ALL to browse/filter all works.
        base = self.work_view if attention_level or review_need is not None else self.queue_view
        frame = self.scoped(base, scope).copy()
        for column, value in (("lifecycle_stage", lifecycle), ("review_priority_band", band),
                              ("sector", sector), ("sub_sector", sub_sector)):
            if value:
                frame = frame.loc[frame[column].astype(str).eq(value)]
        for column, value in (("has_duplicate_review_candidate", duplicate),
                              ("has_compliance_review", compliance),
                              ("already_overdue_as_of", overdue),
                              ("already_over_sanction_as_of", over_sanction)):
            if value is not None:
                frame = frame.loc[self._as_bool(frame[column]).eq(value)]
        if attention_level:
            frame = frame.loc[frame["attention_level"].eq(attention_level)]
        if review_need == "REQUIRES_REVIEW":
            frame = frame.loc[frame["requires_review"]]
        elif review_need == "IMMEDIATE_PRIORITY":
            frame = frame.loc[frame["attention_level"].eq("IMMEDIATE_PRIORITY")]
        if search:
            needle = search.strip().casefold()
            haystack = frame[["work_id", "mp_id", "state_name", "district", "sector", "sub_sector"]].fillna("").astype(str).agg(" ".join, axis=1).str.casefold()
            frame = frame.loc[haystack.str.contains(needle, regex=False)]
        if alert_type:
            ids = {wid for wid in frame["work_id"].astype(str)
                   if any(a.get("alert_type") == alert_type for a in self.artifacts.group("alerts", wid))}
            frame = frame.loc[frame["work_id"].astype(str).isin(ids)]
        statuses = self.reviews.latest_statuses()
        frame["current_review_status"] = frame["work_id"].astype(str).map(statuses).fillna("OPEN")
        if review_status:
            frame = frame.loc[frame["current_review_status"].eq(review_status)]
        allowed_sort = {"score": "review_priority_score_0_100", "rank": "review_priority_rank_overall",
                        "work_id": "work_id", "sanctioned_amount": "sanctioned_amount_inr"}
        column = allowed_sort.get(sort_by, "review_priority_score_0_100")
        ascending = sort_order.casefold() == "asc"
        frame = frame.sort_values([column, "work_id"], ascending=[ascending, True], kind="stable")
        total, start = len(frame), (page - 1) * page_size
        fields = ["work_id", "mp_id", "state_name", "district", "sector", "sub_sector",
                  "lifecycle_stage", "source_current_status", "sanctioned_amount_inr",
                  "review_priority_score_0_100", "review_priority_band", "review_priority_rank_overall",
                  "fusion_evidence_coverage_pct", "top_contributor_1_family", "top_contributor_1_summary",
                  "top_contributor_2_family", "top_contributor_2_summary", "top_contributor_3_family",
                  "top_contributor_3_summary", "has_duplicate_review_candidate", "has_payment_evidence",
                  "has_compliance_review", "already_overdue_as_of", "already_over_sanction_as_of",
                  "attention_level", "requires_review", "current_review_status"]
        items = json_safe(frame.iloc[start:start + page_size][fields].to_dict(orient="records"))
        for item in items:
            item["attention_level_label"] = ATTENTION_LEVEL_LABELS[str(item["attention_level"])]
            alerts = self.artifacts.group("alerts", str(item["work_id"]))
            item["alerts"] = alerts[:3]
            actionable = sorted(
                (alert for alert in alerts if is_actionable_alert(alert.get("alert_type"))),
                key=lambda alert: float(alert.get("alert_strength_0_100") or 0),
                reverse=True,
            )
            item["attention_reasons"] = list(dict.fromkeys(
                ALERT_LABELS.get(str(alert.get("alert_type")), "Needs verification")
                for alert in actionable
            ))[:3] or ["No major current actionable review condition is present."]
        return {"items": items, "page": page, "page_size": page_size, "total": total,
                "total_pages": math.ceil(total / page_size) if total else 0}

    def work_detail(self, work_id: str) -> dict[str, Any]:
        self.artifacts.require_work(work_id)
        features = self.artifacts.get("features", work_id) or {}
        master = self.artifacts.work_master.get(work_id, {})
        mp = self.artifacts.mp_master.get(str(features.get("mp_id")), {})
        entity = self.artifacts.entity_master.get(str(features.get("implementing_agency_id")), {})
        contributions = self.artifacts.group("contributions", work_id)
        score = float((self.artifacts.get("priority", work_id) or {}).get("review_priority_score_0_100", 0))
        contribution_sum = sum(float(item.get("contribution_points") or 0) for item in contributions)
        if not math.isclose(score, contribution_sum, abs_tol=1e-5):
            raise RuntimeError(f"Contribution sum does not reproduce score for {work_id}")
        peers = sorted(self.artifacts.group("peer_evidence", work_id),
                       key=lambda item: float(item.get("absolute_robust_deviation") or 0), reverse=True)[:10]
        duplicates = []
        for pair in self.artifacts.duplicate_pairs.get(work_id, []):
            other_id = pair["work_id_b"] if pair["work_id_a"] == work_id else pair["work_id_a"]
            other = self.artifacts.get("features", str(other_id)) or {}
            other_master = self.artifacts.work_master.get(str(other_id), {})
            duplicates.append({**pair, "paired_work": {**{key: other.get(key) for key in (
                "work_id", "state_name", "district", "sector", "sub_sector", "block", "village",
                "recommended_amount_inr", "sanctioned_amount_inr", "lifecycle_stage",
                "recommendation_date", "sanction_date_as_of")},
                "work_description": other_master.get("work_description"),
                "block": other_master.get("block"), "village": other_master.get("village")}})
        context = self.artifacts.explanations[work_id]
        trend_context = dict(self.artifacts.get("trend_context", work_id) or {})
        trend_key = (
            str(trend_context.get("selected_trend_group_value") or ""),
            str(trend_context.get("strongest_operational_trend_metric") or ""),
        )
        trend_candidates = self._trend_details.get(trend_key, [])
        target_z = float(trend_context.get("strongest_operational_trend_robust_z") or 0)
        if trend_candidates:
            trend_context["display_detail"] = min(
                trend_candidates,
                key=lambda row: abs(float(row.get("robust_z") or 0) - target_z),
            )
        detail = json_safe({
            "profile": {**features, "work_description": master.get("work_description"), "block": master.get("block"),
                        "village": master.get("village"), "latitude": master.get("latitude"), "longitude": master.get("longitude"),
                        "mp_name": mp.get("mp_name"), "implementing_agency_name": entity.get("entity_name")},
            "priority": self.artifacts.get("priority", work_id), "contributions": contributions,
            "contribution_sum": contribution_sum, "alerts": self.artifacts.group("alerts", work_id),
            "anomaly": self.artifacts.get("anomaly", work_id),
            "peer_benchmark": {"summary": self.artifacts.get("peer_summary", work_id), "top_deviations": peers, "returned_limit": 10},
            "duplicates": {"summary": self.artifacts.get("duplicate_summary", work_id), "review_candidates": duplicates},
            "payments": {"summary": self.artifacts.get("payment_summary", work_id), "evidence": self.artifacts.group("payment_evidence", work_id), "fund_progress": self.artifacts.fund_progress.get(work_id)},
            "compliance": {"summary": self.artifacts.get("compliance_summary", work_id), "rules": self.artifacts.group("compliance_evidence", work_id)},
            "prediction": {"scores": self.artifacts.get("prediction", work_id), "explanations": self.artifacts.group("prediction_explanations", work_id),
                           "delay_note": "Delay prediction is unavailable; observed overdue status remains descriptive.",
                           "cost_note": "Cost model has weak discrimination; the raw serving score is secondary review context only."},
            "trend_context": trend_context,
            "explanation": {"generation_mode": "DETERMINISTIC_FALLBACK", "api_status": "OFFLINE_DEFAULT",
                            "explanation": context["fallback_explanation"], "retrieval": context["retrieval"]},
            "reviews": self.reviews.list_for_work(work_id),
            "current_review_status": self.reviews.latest_statuses().get(work_id, "OPEN")})
        detail["presentation"] = json_safe(build_work_presentation(detail))
        return detail

    def _group_allowed(self, group_value: str, scope: Scope) -> bool:
        self._validate_scope(scope)
        if scope.role == Role.MOSPI:
            return True
        if scope.role == Role.MP:
            return False
        if f"state_name={scope.state}" not in group_value:
            return False
        return scope.role != Role.DISTRICT or f"district={scope.district}" in group_value

    def trends(self, scope: Scope, *, metric: str | None, group_type: str | None,
               state: str | None, district: str | None, sector: str | None,
               date_from: str | None, date_to: str | None, limit: int) -> dict[str, Any]:
        frame = self.artifacts.trend_timeseries.copy()
        if scope.role != Role.MOSPI:
            frame = frame.loc[frame["group_value"].astype(str).map(lambda value: self._group_allowed(value, scope))]
        for column, value in (("metric", metric), ("group_type", group_type)):
            if value:
                frame = frame.loc[frame[column].eq(value)]
        for token in (f"state_name={state}" if state else None, f"district={district}" if district else None, f"sector={sector}" if sector else None):
            if token:
                frame = frame.loc[frame["group_value"].astype(str).str.contains(token, regex=False)]
        if date_from:
            frame = frame.loc[frame["month"].astype(str).ge(date_from)]
        if date_to:
            frame = frame.loc[frame["month"].astype(str).le(date_to)]
        frame = frame.sort_values(["group_type", "group_value", "metric", "month"])
        total = len(frame)
        return {"items": json_safe(frame.head(limit).to_dict(orient="records")), "total": total,
                "returned": min(total, limit), "limit": limit}

    def aggregated(self, name: str, scope: Scope, *, group_type: str | None,
                   alert_type: str | None, limit: int) -> dict[str, Any]:
        frame = getattr(self.artifacts, name).copy()
        if scope.role != Role.MOSPI:
            frame = frame.loc[frame["group_value"].astype(str).map(lambda value: self._group_allowed(value, scope))]
        if group_type:
            frame = frame.loc[frame["group_type"].eq(group_type)]
        if alert_type and "alert_type" in frame.columns:
            frame = frame.loc[frame["alert_type"].eq(alert_type)]
        total = len(frame)
        return {"items": json_safe(frame.head(limit).to_dict(orient="records")), "total": total,
                "returned": min(total, limit), "limit": limit}

    def alerts(self, scope: Scope, *, alert_type: str | None,
               lifecycle: str | None, minimum_strength: float, limit: int) -> dict[str, Any]:
        allowed_ids = set(self.scoped(self.work_view, scope)["work_id"].astype(str))
        frame = self.artifacts.group_frames["alerts"]
        frame = frame.loc[frame["work_id"].astype(str).isin(allowed_ids)]
        if alert_type:
            frame = frame.loc[frame["alert_type"].eq(alert_type)]
        if lifecycle:
            frame = frame.loc[frame["lifecycle_stage"].eq(lifecycle)]
        frame = frame.loc[frame["alert_strength_0_100"].ge(minimum_strength)]
        summary = []
        for current_type, group in frame.groupby("alert_type", sort=True):
            current = str(current_type)
            actionable = is_actionable_alert(current)
            summary.append({
                "alert_type": current,
                "category": alert_category(current),
                "label": ALERT_LABELS.get(current, current.replace("_", " ").title()),
                "work_count": int(group["work_id"].astype(str).nunique()),
                "alert_count": int(len(group)),
                "status": "Requires Review" if actionable else "Analytical context",
                "actionable": actionable,
                "short_explanation": ALERT_ACTIONS.get(
                    current,
                    "Use as analytical context and verify the underlying source evidence.",
                ),
            })
        summary.sort(key=lambda item: (item["category"], item["label"]))
        frame = frame.sort_values(["alert_strength_0_100", "work_id", "alert_id"],
                                  ascending=[False, True, True], kind="stable")
        total = len(frame)
        return {"items": json_safe(frame.head(limit).to_dict(orient="records")),
                "summary": summary, "total": total, "returned": min(total, limit), "limit": limit}
