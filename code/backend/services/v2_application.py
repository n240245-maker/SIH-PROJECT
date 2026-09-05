"""Role-aware decision-support services over the synthetic demo-v2 profile."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import date
from typing import Any

import pandas as pd

from backend.repositories.geo_evidence import GeoEvidenceRepository
from backend.repositories.reviews import ReviewRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.schemas import Role
from backend.serialization import json_safe
from backend.services.application import Scope
from intelligence.v2.geo import first_working_days, location_status


ROLE_ORDERS = {
    "MOSPI": ["National Overview", "Morning Ministry Brief", "State Performance", "India Monitoring Map", "Fund Flow Monitoring", "National Project Health", "Top Critical Alerts", "Compliance Monitoring", "State Comparison", "National Analytical Insights", "Recommended Ministry Actions"],
    "STATE": ["State Overview", "Morning State Brief", "Needs State Intervention", "District Performance", "District Monitoring Map", "State Fund Flow", "Project Health", "Compliance Monitoring", "State Analytical Insights", "Recommended State Actions"],
    "DISTRICT": ["District Overview", "Morning District Brief", "Needs District Action", "Block & Implementing Agency Performance", "Project Execution Map", "Fund & Payment Control", "Field Verification & Progress", "Compliance & Escalation Queue", "District Analytical Insights", "Recommended District Actions", "District Decision Workflow"],
    "IA": ["Agency Overview", "Morning IA Brief", "Geo-Tagged Evidence Due", "My Work Execution Queue", "Progress & Milestones", "Fund & Payment Readiness", "Records & Compliance Tasks", "Geo-Evidence History", "Issues Requiring District Support", "Agency Performance", "Recent Submissions & Responses"],
    "MP": ["Constituency Summary", "Morning Brief", "Project Status", "Fund Utilization Flow", "Development by Sector", "Projects Requiring Attention"],
}


def _money(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def _bool(value: Any) -> bool:
    return str(value).casefold() in {"true", "1"}


def _attention(band: str, actionable: bool) -> str:
    if band == "CRITICAL":
        return "Immediate Priority"
    if band == "HIGH":
        return "High-Priority Review"
    if band == "MEDIUM":
        return "Medium Attention"
    return "Low Attention" if actionable else "Normal"


class V2ApplicationService:
    def __init__(
        self,
        artifacts: V2ArtifactRepository,
        reviews: ReviewRepository,
        geo_runtime: GeoEvidenceRepository,
    ) -> None:
        self.artifacts = artifacts
        self.reviews = reviews
        self.geo_runtime = geo_runtime
        self.work_view = artifacts.profile

    @staticmethod
    def _validate_scope(scope: Scope) -> None:
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

    def authorize_work(self, work_id: str, scope: Scope) -> None:
        self.artifacts.require_work(work_id)
        if work_id not in set(self.scoped(self.work_view, scope)["work_id"].astype(str)):
            raise KeyError(work_id)

    def scope_options(self) -> dict[str, Any]:
        districts = self.work_view[["state_name", "district"]].drop_duplicates().sort_values(["state_name", "district"])
        return {
            "roles": [role.value for role in Role],
            "states": sorted(self.work_view["state_name"].dropna().unique().tolist()),
            "districts": json_safe(districts.to_dict(orient="records")),
            "mps": [
                {"mp_id": key, "mp_name": value["mp_name"], "state_name": value["state_name"], "constituency": value["constituency"]}
                for key, value in sorted(self.artifacts.mp_index.items())
            ],
            "agencies": [
                {"agency_id": key, "agency_name": value["entity_name"], "state_name": value["state_name"], "district": value["district"]}
                for key, value in sorted(self.artifacts.entity_index.items())
            ],
            "dataset_profile": "demo_v2",
            "synthetic_demo_data": True,
        }

    @staticmethod
    def _status_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
        completed = frame["lifecycle_stage"].eq("COMPLETION")
        delayed = frame["observed_delay"].astype(str).str.casefold().eq("true")
        ongoing = frame["lifecycle_stage"].eq("EXECUTION") & ~delayed
        return {"COMPLETED": completed, "ONGOING": ongoing, "DELAYED": delayed}

    def _comparison(self, frame: pd.DataFrame, scope: Scope) -> dict[str, Any]:
        if scope.role == Role.MOSPI:
            column, level = "state_name", "State"
        elif scope.role == Role.STATE:
            column, level = "district", "District"
        elif scope.role == Role.DISTRICT:
            column, level = "implementing_agency_id", "Implementing Agency"
        elif scope.role == Role.IA:
            column, level = "block", "Block"
        else:
            column, level = "sector", "Sector"
        rows: list[dict[str, Any]] = []
        for value, group in frame.groupby(column, dropna=False):
            count = len(group)
            utilized = _money(group["final_actual_expenditure_inr"].fillna(group["current_expenditure_inr"]))
            sanctioned = _money(group["sanctioned_amount_inr"])
            high = group["review_priority_band"].isin(["HIGH", "CRITICAL"])
            delayed = group["observed_delay"].astype(str).str.casefold().eq("true")
            closure = group["closure_requires_review"].astype(str).str.casefold().eq("true")
            rows.append({
                "label": str(value), "work_count": count,
                "utilization_pct": round(utilized / sanctioned * 100, 1) if sanctioned else None,
                "completion_rate_pct": round(group["lifecycle_stage"].eq("COMPLETION").mean() * 100, 1),
                "delayed_count": int(delayed.sum()), "delayed_rate_pct": round(delayed.mean() * 100, 1),
                "high_priority_count": int(high.sum()), "high_priority_rate_pct": round(high.mean() * 100, 1),
                "compliance_issue_count": int(closure.sum()), "compliance_issue_rate_pct": round(closure.mean() * 100, 1),
            })
        rows.sort(key=lambda row: (-row["high_priority_count"], row["label"]))
        return {"level": level, "items": rows}

    def overview(self, scope: Scope) -> dict[str, Any]:
        frame = self.scoped(self.work_view, scope).copy()
        masks = self._status_masks(frame)
        utilized_series = pd.to_numeric(frame["final_actual_expenditure_inr"], errors="coerce").fillna(
            pd.to_numeric(frame["current_expenditure_inr"], errors="coerce")
        )
        sanctioned = _money(frame["sanctioned_amount_inr"])
        released = _money(frame["released_payments_inr"])
        utilized = float(utilized_series.fillna(0).sum())
        mp_ids = set(frame["mp_id"].astype(str))
        allocations = self.artifacts.allocations.loc[self.artifacts.allocations["mp_id"].astype(str).isin(mp_ids)]
        current_alloc = allocations.loc[allocations["financial_year"].eq("2026-27")]
        previous_alloc = allocations.loc[allocations["financial_year"].eq("2025-26")]
        allocated = _money(current_alloc["allocated_amount_inr"])
        current_util_pct = _money(current_alloc["utilized_amount_inr"]) / _money(current_alloc["sanctioned_amount_inr"]) * 100 if _money(current_alloc["sanctioned_amount_inr"]) else None
        previous_util_pct = _money(previous_alloc["utilized_amount_inr"]) / _money(previous_alloc["sanctioned_amount_inr"]) * 100 if _money(previous_alloc["sanctioned_amount_inr"]) else None
        high = frame["review_priority_band"].isin(["HIGH", "CRITICAL"])
        actionable = frame["requires_review"].astype(str).str.casefold().eq("true")
        geo_due = frame["monthly_evidence_status"].eq("OVERDUE")
        closure = frame["closure_requires_review"].astype(str).str.casefold().eq("true")
        role_name = "Ministry" if scope.role == Role.MOSPI else scope.role.value
        brief = [
            f"{len(frame):,} scoped works are available for {role_name} review.",
            f"{int(high.sum()):,} are in the High-Priority Review queue and {int(masks['DELAYED'].sum()):,} have an observed delay.",
            f"{int(geo_due.sum()):,} execution works have overdue current-month site evidence; this warning does not add Review Priority points.",
            f"{int(closure.sum()):,} completed works require closure-record follow-up.",
        ]
        sectors = []
        for sector, group in frame.groupby("sector"):
            amount = _money(group["sanctioned_amount_inr"])
            sectors.append({"sector": str(sector), "sanctioned_amount_inr": amount, "share_pct": round(amount / sanctioned * 100, 1) if sanctioned else 0})
        sectors.sort(key=lambda row: -row["sanctioned_amount_inr"])
        top = frame.sort_values(["review_priority_score_0_100", "work_id"], ascending=[False, True]).head(10)
        latest_statuses = self.reviews.latest_statuses()
        top_rows = []
        for row in top.to_dict(orient="records"):
            top_rows.append({
                "work_id": row["work_id"], "project": row["work_description"],
                "location": f"{row['village']}, {row['district']}",
                "main_issue": (self.artifacts.group("alerts", str(row["work_id"])) or [{"message": "Unusual pattern for officer review."}])[0]["message"],
                "status": row["current_status"], "review_priority": row["review_priority_score_0_100"],
                "review_priority_band": row["review_priority_band"],
                "officer_case_status": latest_statuses.get(str(row["work_id"]), "OPEN"),
            })
        comparison = self._comparison(frame, scope)
        return json_safe({
            "dataset_profile": "demo_v2", "synthetic_demo_data": True,
            "synthetic_disclaimer": self.artifacts.dataset_metadata["disclaimer"],
            "scope": asdict(scope), "role": scope.role.value,
            "section_order": ROLE_ORDERS[scope.role.value],
            "primary_question": {
                "MOSPI": "How is MPLADS performing nationally and which states require national-level intervention?",
                "STATE": "Which districts, projects and compliance issues need state-level intervention today?",
                "DISTRICT": "Which works, agencies, payments and field issues need district-level action today?",
                "IA": "Which works must my agency update, photograph, document, or resolve today?",
                "MP": "What is happening in my constituency and what needs my attention?",
            }[scope.role.value],
            "overview": {
                "mplads_locations": int(frame[["district", "block", "village"]].drop_duplicates().shape[0]),
                "total_projects": len(frame), "allocated_amount_inr": allocated,
                "sanctioned_amount_inr": sanctioned, "released_amount_inr": released,
                "utilized_amount_inr": utilized, "remaining_balance_inr": released - utilized,
                "utilization_pct_of_sanction": round(utilized / sanctioned * 100, 1) if sanctioned else None,
                "completed": int(masks["COMPLETED"].sum()), "ongoing": int(masks["ONGOING"].sum()),
                "delayed": int(masks["DELAYED"].sum()), "high_priority_review": int(high.sum()),
                "works_requiring_review": int(actionable.sum()), "site_evidence_overdue": int(geo_due.sum()),
                "pending_compliance_issues": int(closure.sum()),
            },
            "morning_brief": {"generation_mode": "DETERMINISTIC_STRUCTURED", "facts": brief, "ai_explicit_action_only": True},
            "project_status": {key: int(mask.sum()) for key, mask in masks.items()},
            "high_priority_overlap_count": int(high.sum()),
            "fund_flow": {
                "allocated_amount_inr": allocated, "sanctioned_amount_inr": sanctioned,
                "released_amount_inr": released, "utilized_amount_inr": utilized,
                "unspent_released_amount_inr": released - utilized,
                "utilization_formula": "Utilized / Sanctioned × 100",
                "current_year_utilization_pct": current_util_pct,
                "previous_year_utilization_pct": previous_util_pct,
                "percentage_point_change": current_util_pct - previous_util_pct if current_util_pct is not None and previous_util_pct is not None else None,
            },
            "sector_distribution": sectors,
            "comparison": comparison,
            "map": {
                "rendering": "ACCESSIBLE_HEAT_TABLE_FALLBACK",
                "license_note": "No external GeoJSON or live map API is used; rows are computed from clearly synthetic demo-v2 scope data.",
                "layer_options": ["Fund Utilization", "Delayed Works", "Cost Overrun Alerts", "High-Priority Review Cases", "Compliance Issues"],
                "items": comparison["items"],
            },
            "projects_requiring_attention": top_rows[:5] if scope.role == Role.MP else top_rows,
            "recommended_actions": ["Verify underlying project evidence", "Request clarification or supporting records", "Schedule field verification where appropriate", "Escalate only after authorized human review"],
            "decision_workflow": ["SIGNAL", "VERIFY", "ACT", "ESCALATE IF REQUIRED"],
            "language_note": "Anomaly and Review Priority support human review; neither is a finding of fraud or wrongdoing.",
        })

    def review_queue(self, scope: Scope, *, page: int, page_size: int, search: str | None = None, **filters: Any) -> dict[str, Any]:
        frame = self.scoped(self.work_view, scope).copy()
        if search:
            needle = search.casefold()
            frame = frame.loc[
                frame["work_id"].astype(str).str.casefold().str.contains(needle, regex=False)
                | frame["work_description"].astype(str).str.casefold().str.contains(needle, regex=False)
            ]
        mapping = {"lifecycle": "lifecycle_stage", "band": "review_priority_band", "sector": "sector", "sub_sector": "sub_sector"}
        for parameter, column in mapping.items():
            if filters.get(parameter):
                frame = frame.loc[frame[column].eq(filters[parameter])]
        if filters.get("review_need") not in {None, "ALL"}:
            frame = frame.loc[frame["requires_review"].astype(str).str.casefold().eq("true")]
        frame = frame.sort_values(["review_priority_score_0_100", "work_id"], ascending=[False, True])
        total = len(frame)
        start = (page - 1) * page_size
        items = frame.iloc[start:start + page_size].copy()
        items["attention_level"] = items.apply(
            lambda row: _attention(str(row["review_priority_band"]), _bool(row["requires_review"])), axis=1
        )
        fields = [
            "work_id", "mp_id", "state_name", "district", "sector", "sub_sector",
            "lifecycle_stage", "current_status", "sanctioned_amount_inr",
            "review_priority_score_0_100", "review_priority_band", "requires_review",
            "attention_level", "observed_delay", "observed_cost_overrun",
            "has_duplicate_candidate", "monthly_evidence_status",
        ]
        return {"items": json_safe(items[fields].to_dict(orient="records")), "page": page, "page_size": page_size, "total": total, "total_pages": math.ceil(total / page_size) if total else 0}

    def _geo_history(self, work: dict[str, Any]) -> list[dict[str, Any]]:
        work_id = str(work["work_id"])
        seeded = self.artifacts.group("geo", work_id)
        runtime = self.geo_runtime.list_for_work(work_id)
        rows = []
        for item in [*seeded, *runtime]:
            month = str(item.get("reporting_month") or "")
            capture = str(item.get("capture_timestamp") or "")[:10]
            required_window = None
            status = "RECORDED"
            if item.get("evidence_stage") == "MONTHLY_PROGRESS" and month:
                year, month_number = map(int, month.split("-"))
                window = first_working_days(year, month_number)
                required_window = f"{window[0].isoformat()} to {window[-1].isoformat()}"
                status = "SUBMITTED_LATE" if capture and date.fromisoformat(capture) > window[-1] else "RECORDED"
            loc_state, distance = location_status(
                work.get("registered_latitude"), work.get("registered_longitude"),
                item.get("latitude"), item.get("longitude"),
            )
            rows.append({
                **item, "required_window": required_window, "window_status": status,
                "location_status": loc_state, "distance_from_registered_metres": distance,
                "image_url": f"/api/v2/geo-evidence/{item['evidence_id']}/image",
            })
        rows.sort(key=lambda item: str(item.get("capture_timestamp") or ""), reverse=True)
        return json_safe(rows)

    def work_detail(self, work_id: str) -> dict[str, Any]:
        work = self.artifacts.require_work(work_id)
        alerts = self.artifacts.group("alerts", work_id)
        payments = sorted(self.artifacts.group("payments", work_id), key=lambda row: (row.get("payment_release_date") or "", int(row.get("payment_stage") or 0), row.get("payment_id") or ""))
        progress = sorted(self.artifacts.group("progress", work_id), key=lambda row: row.get("report_date") or "")
        records = self.artifacts.group("records", work_id)
        contributions = self.artifacts.group("priority_evidence", work_id)
        geo_history = self._geo_history(work)
        actionable = _bool(work.get("requires_review"))
        band = str(work.get("review_priority_band"))
        released = float(work.get("released_payments_inr") or 0)
        sanctioned = float(work.get("sanctioned_amount_inr") or 0)
        difference = released - sanctioned
        exceed_pct = difference / sanctioned * 100 if sanctioned else None
        gap = float(work.get("financial_physical_gap_pct") or 0)
        duplicate_pairs = []
        for pair in self.artifacts.duplicate_pairs.get(work_id, []):
            other_id = str(pair["work_id_b"] if pair["work_id_a"] == work_id else pair["work_id_a"])
            other = self.artifacts.require_work(other_id)
            duplicate_pairs.append({
                **pair,
                "candidate_work": {key: other.get(key) for key in (
                    "work_id", "work_description", "state_name", "district", "block", "village",
                    "sanctioned_amount_inr", "recommendation_date", "sanction_date",
                    "implementing_agency_id", "lifecycle_stage",
                )},
            })
        timeline = [
            {"label": "Recommendation", "date": work.get("recommendation_date"), "kind": "RECORDED"},
            {"label": "Sanction", "date": work.get("sanction_date"), "kind": "RECORDED"},
            {"label": "Expected Start", "date": work.get("expected_start_date"), "kind": "PLANNED"},
            {"label": "Actual Start", "date": work.get("actual_start_date"), "kind": "RECORDED"},
        ]
        if progress:
            timeline.extend([
                {"label": "First Progress Report", "date": progress[0]["report_date"], "kind": "RECORDED"},
                {"label": "Latest Progress Report", "date": progress[-1]["report_date"], "kind": "RECORDED"},
            ])
        timeline.extend([
            {"label": "Expected Completion", "date": work.get("expected_completion_date"), "kind": "PLANNED"},
            {"label": "Recorded Completion", "date": work.get("actual_completion_date"), "kind": "RECORDED"},
        ])
        timeline = [item for item in timeline if item["date"]]
        timeline.sort(key=lambda item: str(item["date"]))

        monitoring = [
            {"label": "Fund Utilization", "status": "Very High Attention" if exceed_pct is not None and exceed_pct > 30 else "Requires Review" if difference > 0 else "Normal", "target": "key-risk-areas"},
            {"label": "Physical Progress", "status": "Requires Review" if gap > 25 else "Normal", "target": "anomalies"},
            {"label": "Schedule", "status": "Observed Delay" if _bool(work.get("observed_delay")) else "On Schedule", "target": "progress-schedule"},
            {"label": "Payments", "status": "Requires Review" if _bool(work.get("payment_chronology_flag")) else "Normal", "target": "key-risk-areas"},
            {"label": "Compliance", "status": "Requires Review" if _bool(work.get("closure_requires_review")) else "Normal", "target": "records"},
            {"label": "Duplicate Review", "status": "Requires Comparison" if duplicate_pairs else "Normal", "target": "key-risk-areas"},
            {"label": "Completion Records", "status": "Requires Review" if _bool(work.get("closure_requires_review")) else "Not yet due" if work.get("lifecycle_stage") != "COMPLETION" else "Recorded", "target": "records"},
            {"label": "Evidence Availability", "status": "Requires Review" if work.get("monthly_evidence_status") == "OVERDUE" else "Good", "target": "geo-evidence"},
        ]
        anomalies = []
        if gap > 25:
            anomalies.append({"title": "Financial progress is significantly ahead of physical progress", "value": f"{gap:.1f} percentage-point difference", "status": "Requires Review"})
        if _bool(work.get("payment_chronology_flag")):
            first = next((row for row in payments if str(row["authorization_date"]) < str(row["payment_request_date"])), payments[0] if payments else {})
            anomalies.append({"title": "Payment chronology is unusual", "value": f"Authorization {first.get('authorization_date')} · Request {first.get('payment_request_date')}", "status": "Requires Review"})
        if _bool(work.get("observed_delay")):
            anomalies.append({"title": "The expected completion date has passed", "value": str(work.get("expected_completion_date")), "status": "Observed Delay"})
        if _bool(work.get("observed_cost_overrun")):
            anomalies.append({"title": "Final expenditure is above the sanctioned amount", "value": "Observed Cost Overrun", "status": "Observed Condition"})
        if not anomalies:
            anomalies.append({"title": "No direct operational irregularity is currently flagged", "value": "Continue routine monitoring", "status": "Normal"})

        record_fields = [
            "sanction_record", "progress_report", "payment_release", "completion_certificate",
            "utilization_certificate", "handover_record", "public_use_evidence",
            "completed_work_photo", "asset_register", "audit_record",
        ]
        record_status = {field: work.get(field) for field in record_fields}
        issue_summaries = [str(item["message"]) for item in alerts]
        fallback = {
            "what_the_work_is": f"{work['work_description']} in {work['village']}, {work['district']}.",
            "what_happened": issue_summaries[:3] or ["No current actionable condition is recorded."],
            "main_issues": issue_summaries[:5],
            "generation_mode": "DETERMINISTIC_FALLBACK",
        }
        return json_safe({
            "dataset_profile": "demo_v2", "synthetic_demo_data": True,
            "synthetic_disclaimer": self.artifacts.dataset_metadata["disclaimer"],
            "header": {
                "workspace": "Officer case workspace", "work_id": work_id,
                "project_title": work["work_description"],
                "location": f"{work['village']}, {work['block']}, {work['district']}, {work['state_name']}",
                "attention_level": _attention(band, actionable), "requires_review": actionable,
                "review_priority_score_0_100": work["review_priority_score_0_100"], "internal_band": band,
            },
            "project_details": {
                "work_id": work_id, "lifecycle": work["lifecycle_stage"], "recorded_work_status": work["current_status"],
                "officer_case_status": self.reviews.latest_statuses().get(work_id, "OPEN"),
                "member_of_parliament": self.artifacts.mp_index[str(work["mp_id"])]["mp_name"],
                "mp_id": work["mp_id"], "constituency": work["constituency"],
                "location": f"{work['village']}, {work['block']}, {work['district']}, {work['state_name']}",
                "sanctioned_amount_inr": work["sanctioned_amount_inr"], "released_payments_inr": released,
                "physical_progress_pct": work["physical_progress_pct"], "financial_progress_pct": work["financial_progress_pct"],
                "completion_recorded": work.get("actual_completion_date"),
                "field_highlights": {"released_payments_inr": difference > 0},
            },
            "monitoring_health": monitoring,
            "anomalies_irregularities": anomalies,
            "key_risk_areas": {
                "fund_utilization": {"status": monitoring[0]["status"], "sanctioned_amount_inr": sanctioned, "released_amount_inr": released, "recorded_expenditure_inr": work.get("current_expenditure_inr"), "difference_inr": difference, "release_above_sanction_pct": exceed_pct, "physical_progress_pct": work.get("physical_progress_pct"), "financial_progress_pct": work.get("financial_progress_pct"), "financial_physical_gap_pct": gap, "payment_count": work.get("payment_count"), "evidence": payments[-20:]},
                "delays": {"status": monitoring[2]["status"], "expected_start": work.get("expected_start_date"), "actual_start": work.get("actual_start_date"), "expected_completion": work.get("expected_completion_date"), "recorded_completion": work.get("actual_completion_date"), "progress_history": progress[-18:]},
                "cost_overrun": {"observed_status": "OBSERVED_COST_OVERRUN" if _bool(work.get("observed_cost_overrun")) else "NO_OBSERVED_COST_OVERRUN", "early_warning_status": work.get("early_warning_status") or "UNAVAILABLE", "technical": {"model": work.get("model_name"), "version": work.get("model_version"), "quality": work.get("model_quality_status"), "evaluation_label": self.artifacts.cost_evaluation["evaluation_label"], "test_metrics": self.artifacts.cost_evaluation["candidate_metrics"][self.artifacts.cost_evaluation["selected_model"]]["test"], "limitations": self.artifacts.cost_evaluation["limitations"]}},
                "duplicate_works": {"status": "CANDIDATE_FOUND" if duplicate_pairs else "NO_CANDIDATE", "candidates": duplicate_pairs, "disclaimer": "This is a duplicate-work candidate for review. It is not confirmation that the works are duplicates.", "technical": {"model": "sentence-transformers/all-MiniLM-L6-v2", "retrieval": "local top-5 nearest neighbours", "candidate_threshold": self.artifacts.duplicate_evaluation["candidate_threshold"], "corroboration": self.artifacts.duplicate_evaluation["corroboration"], "candidate_is_not_confirmation": True}},
            },
            "progress_schedule": {"timeline": timeline, "latest_progress": progress[-1] if progress else None, "chronology": "Events are date-ordered; planned and recorded events remain distinct."},
            "geo_evidence": {"summary": {"current_month_status": work.get("monthly_evidence_status"), "latest_capture": work.get("latest_capture_timestamp"), "location_status": work.get("location_status"), "latest_physical_progress_pct": geo_history[0].get("physical_progress_pct") if geo_history else None, "late_evidence_count": work.get("late_evidence_count"), "warning_contribution_points": 0}, "items": geo_history, "prototype_rule": "Execution works require one site image in the first three Monday-Friday working days of each month. Official State holiday calendars are not included.", "integrity_note": "An image hash proves stored-file integrity; it does not prove image authenticity."},
            "records_completion": {"lifecycle": work["lifecycle_stage"], "completion_readiness": "REQUIRES_REVIEW" if _bool(work.get("closure_requires_review")) else "NOT_YET_DUE" if work["lifecycle_stage"] != "COMPLETION" else "RECORDED", "statuses": record_status, "records": records, "compliance_details": [item for item in alerts if item["alert_type"] == "COMPLETION_RECORDS_REVIEW"]},
            "ai_explanation": {"work_id": work_id, "project_title": work["work_description"], "explanation": fallback, "explicit_click_only": True, "provider": "Groq", "model": "openai/gpt-oss-120b", "method": "Grounded RAG", "retrieval": "MiniLM guideline embeddings", "fallback": "deterministic local explanation"},
            "officer_review": {"current_status": self.reviews.latest_statuses().get(work_id, "OPEN"), "reviews": self.reviews.list_for_work(work_id), "append_only": True, "human_authority_final": True},
            "technical_details": {"anomaly": {"model": "Isolation Forest", "lifecycle": work["lifecycle_stage"], "percentile": work["within_lifecycle_percentile_0_100"], "peer_robust_deviation": work.get("peer_robust_deviation"), "interpretation": "Unusualness, not fraud."}, "review_priority": {"policy": {key: self.artifacts.policy[key] for key in ("policy_version", "based_on", "geo_evidence", "language", "weights")}, "contributions": contributions}, "payment_order": "release date, numeric stage, payment ID"},
        })

    def create_geo_evidence(self, work_id: str, scope: Scope, payload: dict[str, Any]) -> dict[str, Any]:
        self.authorize_work(work_id, scope)
        if scope.role != Role.IA or scope.agency_id != self.artifacts.require_work(work_id)["implementing_agency_id"]:
            raise PermissionError("Only the assigned Implementing Agency may submit evidence")
        return self.geo_runtime.create(work_id, payload, agency_id=str(scope.agency_id))

    def verify_geo_evidence(self, evidence_id: str, scope: Scope, payload: dict[str, Any]) -> dict[str, Any]:
        if scope.role != Role.DISTRICT:
            raise PermissionError("District authority verification is required")
        submission = next((row for row in self.geo_runtime._rows(self.geo_runtime.submissions_path) if row["evidence_id"] == evidence_id), None)
        if submission is None:
            raise KeyError(evidence_id)
        self.authorize_work(str(submission["work_id"]), scope)
        return self.geo_runtime.verify(evidence_id, payload)

    def alerts(self, scope: Scope, *, limit: int = 200, **_: Any) -> dict[str, Any]:
        allowed = set(self.scoped(self.work_view, scope)["work_id"].astype(str))
        all_rows = self.artifacts.rows_for_work_ids("alerts", allowed)
        grouped: dict[str, dict[str, Any]] = {}
        for row in all_rows:
            alert_type = str(row.get("alert_type") or "OTHER_REVIEW_SIGNAL")
            current = grouped.setdefault(alert_type, {
                "alert_type": alert_type, "alert_count": 0, "work_ids": set(),
                "message": row.get("message"),
            })
            current["alert_count"] += 1
            current["work_ids"].add(str(row.get("work_id")))
        summary = [
            {**value, "work_count": len(value.pop("work_ids"))}
            for _, value in sorted(grouped.items())
        ]
        rows = all_rows[:limit]
        return {"items": rows, "summary": summary, "total": len(all_rows), "returned": len(rows), "limit": limit}
