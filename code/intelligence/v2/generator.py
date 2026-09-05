"""Generate a deterministic, clearly synthetic MPLADS demonstration dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from intelligence.data.paths import ProjectPaths
from intelligence.v2.geo import first_working_days, haversine_metres


SEED = 26102
WORK_COUNT = 5_000
AS_OF_DATE = date(2026, 9, 5)
GENERATED_AT = "2026-09-05T00:00:00+00:00"
SYNTHETIC_NOTICE = (
    "SYNTHETIC DEMO DATA — generated for prototype testing; distributions and coordinates "
    "do not represent real MPLADS national prevalence or Government field evidence."
)

STATES = {
    "Andhra Pradesh": (15.3, 79.7),
    "Karnataka": (15.3, 75.7),
    "Maharashtra": (19.4, 75.0),
    "Odisha": (20.5, 84.4),
    "Rajasthan": (26.6, 73.8),
    "Tamil Nadu": (11.1, 78.7),
}
SECTORS = {
    "Roads": ["rural road", "approach road", "culvert improvement"],
    "Education": ["school classroom", "college laboratory", "library building"],
    "Drinking Water": ["drinking water pipeline", "community water tank", "borewell system"],
    "Health": ["primary health centre", "diagnostic room", "community clinic"],
    "Community Infrastructure": ["community hall", "public shelter", "sports facility"],
    "Others": ["solar street lighting", "public sanitation block", "drainage improvement"],
}

REPRESENTATIVE_CASES = {
    "normal_work": "W-000101",
    "observed_delay": "W-000202",
    "fund_utilization_mismatch": "W-000303",
    "payment_chronology_irregularity": "W-000404",
    "observed_cost_overrun": "W-000505",
    "cost_overrun_early_warning": "W-000606",
    "duplicate_candidate_a": "W-000707",
    "duplicate_candidate_b": "W-000708",
    "missing_monthly_geo_evidence": "W-000808",
    "late_geo_evidence": "W-000909",
    "location_requires_review": "W-001010",
    "completed_full_closure": "W-001111",
    "completed_missing_closure": "W-001212",
    "deterministic_compliance_issue": "W-001313",
    "multi_signal_high_priority": "W-001937",
    "legacy_execution_demo": "W-002760",
}

SCENARIO_BY_WORK = {
    work_id: scenario for scenario, work_id in REPRESENTATIVE_CASES.items()
}


def _iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _money(value: float) -> int:
    return int(round(value / 1_000) * 1_000)


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not columns:
        raise ValueError(f"Cannot infer columns for empty output {path}")
    fieldnames = columns or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _month_starts(start: date, end: date) -> Iterable[date]:
    cursor = start.replace(day=1)
    while cursor <= end:
        yield cursor
        cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _lifecycle(index: int, scenario: str | None) -> str:
    if scenario in {"observed_delay", "fund_utilization_mismatch", "payment_chronology_irregularity", "cost_overrun_early_warning", "missing_monthly_geo_evidence", "late_geo_evidence", "location_requires_review", "legacy_execution_demo"}:
        return "EXECUTION"
    if scenario in {"normal_work", "observed_cost_overrun", "duplicate_candidate_a", "duplicate_candidate_b", "completed_full_closure", "completed_missing_closure", "deterministic_compliance_issue", "multi_signal_high_priority"}:
        return "COMPLETION"
    bucket = index % 20
    return "PRE_SANCTION" if bucket < 2 else "EXECUTION" if bucket < 9 else "COMPLETION"


def _svg_assets(output: Path) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    image_dir = output / "evidence-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    colors = [("navy", "#12365b"), ("green", "#25634d"), ("orange", "#a95b16")]
    for index, (name, color) in enumerate(colors, 1):
        path = image_dir / f"synthetic-site-{index:02d}.svg"
        content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" role="img" aria-label="Synthetic demo site evidence">
<rect width="640" height="400" fill="#eef3f7"/><rect x="28" y="28" width="584" height="344" rx="18" fill="white" stroke="{color}" stroke-width="5"/>
<path d="M90 285 L220 170 L310 245 L410 120 L550 285 Z" fill="{color}" opacity="0.32"/>
<text x="320" y="70" text-anchor="middle" font-family="Arial" font-size="26" font-weight="700" fill="{color}">SYNTHETIC DEMO EVIDENCE</text>
<text x="320" y="330" text-anchor="middle" font-family="Arial" font-size="18" fill="#334155">Prototype image {index} — not a Government field photograph</text></svg>'''
        path.write_text(content, encoding="utf-8")
        assets.append({"path": path.relative_to(output).as_posix(), "sha256": _sha256(path), "name": name})
    return assets


def generate(output: Path, *, work_count: int = WORK_COUNT, seed: int = SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    assets = _svg_assets(output)

    mp_rows: list[dict[str, Any]] = []
    entity_rows: list[dict[str, Any]] = []
    mp_lookup: dict[tuple[str, int], str] = {}
    agencies_by_district: dict[tuple[str, str], list[str]] = defaultdict(list)
    for state_index, state in enumerate(STATES, 1):
        state_code = f"S{state_index:02d}"
        for constituency_index in range(1, 4):
            mp_id = f"MP-{state_code}-{constituency_index:02d}"
            constituency = f"{state} Demo Constituency {constituency_index}"
            mp_lookup[(state, constituency_index)] = mp_id
            mp_rows.append({
                "mp_id": mp_id, "mp_name": f"Demo MP {state_code}-{constituency_index:02d}",
                "state_name": state, "constituency": constituency,
                "annual_entitlement_inr": 50_000_000, "source_type": "SYNTHETIC_V2",
                "synthetic_demo_data": True,
            })
        for district_index in range(1, 4):
            district = f"{state} Demo District {district_index}"
            for agency_index in range(1, 4):
                entity_id = f"IA-{state_code}-{district_index:02d}-{agency_index:02d}"
                agencies_by_district[(state, district)].append(entity_id)
                entity_rows.append({
                    "entity_id": entity_id, "entity_type": "IMPLEMENTING_AGENCY",
                    "entity_name": f"Demo Implementing Agency {state_code}-{district_index:02d}-{agency_index:02d}",
                    "state_name": state, "district": district, "active_status": "ACTIVE",
                    "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
                })

    works: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    progress: list[dict[str, Any]] = []
    assets_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    geo_rows: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    work_context: dict[str, dict[str, Any]] = {}
    payment_index = progress_index = evidence_index = record_index = asset_index = 0

    state_names = list(STATES)
    sector_names = list(SECTORS)
    for index in range(1, work_count + 1):
        work_id = f"W-{index:06d}"
        scenario = SCENARIO_BY_WORK.get(work_id)
        lifecycle = _lifecycle(index, scenario)
        state = state_names[(index - 1) % len(state_names)]
        constituency_index = ((index - 1) // len(state_names)) % 3 + 1
        district_index = ((index - 1) // (len(state_names) * 3)) % 3 + 1
        district = f"{state} Demo District {district_index}"
        block = f"Demo Block {((index - 1) % 5) + 1}"
        village = f"Demo Village {((index * 7) % 41) + 1}"
        mp_id = mp_lookup[(state, constituency_index)]
        # The state/district cycles are correlated with the raw work index, so
        # using ``index % 3`` would assign every district to just one of its
        # three agencies. Advance the agency on each complete 54-work
        # state/district/constituency cycle instead, which distributes works
        # across all synthetic agencies while remaining deterministic.
        agency_id = agencies_by_district[(state, district)][((index - 1) // 54) % 3]
        sector = sector_names[(index * 5 + index // 17) % len(sector_names)]
        sub_sector = SECTORS[sector][index % len(SECTORS[sector])]
        description = f"Construction and improvement of {sub_sector} at {village}, {block}"
        if scenario in {"duplicate_candidate_a", "duplicate_candidate_b"}:
            description = "Construction of community drinking water tank near central school campus"
            sector, sub_sector = "Drinking Water", "community water tank"
        if scenario == "multi_signal_high_priority":
            description = "Improvement of rural approach road and culvert near community school"
        base_lat, base_lon = STATES[state]
        latitude = round(base_lat + ((index % 29) - 14) * 0.012 + rng.uniform(-0.003, 0.003), 6)
        longitude = round(base_lon + ((index % 31) - 15) * 0.012 + rng.uniform(-0.003, 0.003), 6)

        recommendation_date = date(2022, 4, 1) + timedelta(days=(index * 11) % 1_130)
        estimate = _money(rng.uniform(600_000, 12_000_000))
        recommended = _money(estimate * rng.uniform(0.92, 1.08))
        sanctioned = _money(estimate * rng.uniform(0.88, 1.07)) if lifecycle != "PRE_SANCTION" else 0
        sanction_date = recommendation_date + timedelta(days=rng.randint(20, 110)) if sanctioned else None
        expected_start = sanction_date + timedelta(days=rng.randint(15, 65)) if sanction_date else None
        actual_start = expected_start + timedelta(days=rng.randint(-5, 40)) if expected_start and lifecycle != "PRE_SANCTION" else None
        planned_days = rng.randint(150, 500)
        expected_completion = expected_start + timedelta(days=planned_days) if expected_start else None
        actual_completion: date | None = None
        if lifecycle == "COMPLETION" and actual_start and expected_completion:
            actual_completion = expected_completion + timedelta(days=rng.randint(-45, 150))
            actual_completion = min(actual_completion, AS_OF_DATE - timedelta(days=5))
        if lifecycle == "EXECUTION" and actual_start:
            actual_start = min(actual_start, AS_OF_DATE - timedelta(days=75))
            if scenario == "observed_delay":
                expected_completion = AS_OF_DATE - timedelta(days=120)
            elif expected_completion and expected_completion < AS_OF_DATE and rng.random() > 0.28:
                expected_completion = AS_OF_DATE + timedelta(days=rng.randint(20, 240))

        early_pressure = (
            (estimate / max(sanctioned, 1) - 1) * 2.4
            + (planned_days < 230) * 0.35
            + rng.gauss(0, 0.8)
        ) if sanctioned else -2
        overrun_probability = 1 / (1 + math.exp(-(-1.35 + early_pressure)))
        overrun = lifecycle == "COMPLETION" and rng.random() < overrun_probability
        if scenario in {"observed_cost_overrun", "multi_signal_high_priority"}:
            overrun = True
        if scenario in {"normal_work", "completed_full_closure"}:
            overrun = False
        final_expenditure = ""
        if lifecycle == "COMPLETION":
            ratio = rng.uniform(1.04, 1.34) if overrun else rng.uniform(0.82, 1.0)
            final_expenditure = _money(sanctioned * ratio)

        if lifecycle == "PRE_SANCTION":
            current_progress, current_expenditure, status = 0.0, 0, "RECOMMENDED"
        elif lifecycle == "EXECUTION":
            elapsed = max(0.1, min(0.92, (AS_OF_DATE - actual_start).days / max(planned_days, 1)))
            current_progress = round(_clamp(elapsed * 100 + rng.gauss(-2, 12), 3, 92), 1)
            if scenario == "observed_delay":
                current_progress = 44.0
            financial_ratio = _clamp(current_progress / 100 + rng.gauss(0.04, 0.12), 0.05, 1.45)
            current_expenditure = _money(sanctioned * financial_ratio)
            status = "ONGOING"
        else:
            current_progress, current_expenditure, status = 100.0, int(final_expenditure), "COMPLETED"

        if scenario in {"fund_utilization_mismatch", "legacy_execution_demo"}:
            current_progress = 28.9
            current_expenditure = _money(sanctioned * 1.35)
        if scenario == "cost_overrun_early_warning":
            current_progress = 46.0
            current_expenditure = _money(sanctioned * 0.76)

        # Controlled generic anomalies provide a non-trivial evaluation set. The
        # overlap/noise above remains, so these labels are not perfectly separable.
        generic_fund_gap = lifecycle == "EXECUTION" and index % 47 == 0
        generic_payment_chronology = lifecycle != "PRE_SANCTION" and index % 131 == 0
        generic_schedule_irregularity = lifecycle == "EXECUTION" and index % 89 == 0
        generic_geo_missing = lifecycle == "EXECUTION" and index % 29 == 0
        generic_geo_late = lifecycle == "EXECUTION" and index % 43 == 0
        generic_location_review = lifecycle == "EXECUTION" and index % 71 == 0
        if generic_fund_gap:
            current_progress = round(rng.uniform(18, 48), 1)
            current_expenditure = _money(sanctioned * rng.uniform(0.78, 1.18))
        if generic_schedule_irregularity and expected_completion:
            expected_completion = AS_OF_DATE - timedelta(days=rng.randint(30, 220))

        work = {
            "work_id": work_id, "mp_id": mp_id, "state_name": state,
            "constituency": f"{state} Demo Constituency {constituency_index}",
            "district": district, "block": block, "village": village,
            "sector": sector, "sub_sector": sub_sector, "work_description": description,
            "registered_latitude": latitude, "registered_longitude": longitude,
            "coordinates_provenance": "SYNTHETIC_PROTOTYPE_COORDINATE",
            "recommendation_date": _iso(recommendation_date), "recommended_amount_inr": recommended,
            "technical_estimate_amount_inr": estimate, "sanctioned_amount_inr": sanctioned or "",
            "sanction_date": _iso(sanction_date), "sanction_revision_count": int(rng.random() < 0.09) if sanctioned else 0,
            "implementing_agency_id": agency_id, "expected_start_date": _iso(expected_start),
            "actual_start_date": _iso(actual_start), "expected_completion_date": _iso(expected_completion),
            "actual_completion_date": _iso(actual_completion), "lifecycle_stage": lifecycle,
            "current_status": status, "current_physical_progress_pct": current_progress,
            "current_expenditure_inr": current_expenditure, "final_actual_expenditure_inr": final_expenditure,
            "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
        }
        works.append(work)
        work_context[work_id] = {
            **work, "scenario": scenario, "overrun": overrun,
            "generic_fund_gap": generic_fund_gap,
            "generic_payment_chronology": generic_payment_chronology,
            "generic_schedule_irregularity": generic_schedule_irregularity,
            "generic_geo_missing": generic_geo_missing,
            "generic_geo_late": generic_geo_late,
            "generic_location_review": generic_location_review,
        }

        anomaly_types: list[str] = []
        if scenario in {"fund_utilization_mismatch", "legacy_execution_demo", "multi_signal_high_priority"}:
            anomaly_types.append("FUND_PROGRESS_MISMATCH")
        if scenario in {"payment_chronology_irregularity", "legacy_execution_demo", "multi_signal_high_priority"}:
            anomaly_types.append("PAYMENT_CHRONOLOGY")
        if scenario in {"observed_delay", "multi_signal_high_priority"}:
            anomaly_types.append("OBSERVED_DELAY")
        if scenario in {"observed_cost_overrun", "multi_signal_high_priority"}:
            anomaly_types.append("OBSERVED_COST_OVERRUN")
        if generic_fund_gap:
            anomaly_types.append("FUND_PROGRESS_MISMATCH")
        if generic_payment_chronology:
            anomaly_types.append("PAYMENT_CHRONOLOGY")
        if generic_schedule_irregularity:
            anomaly_types.append("OBSERVED_DELAY")
        if generic_geo_missing:
            anomaly_types.append("MISSING_MONTHLY_SITE_EVIDENCE")
        if generic_location_review:
            anomaly_types.append("LOCATION_REQUIRES_REVIEW")
        duplicate_group = "DUP-V2-001" if scenario in {"duplicate_candidate_a", "duplicate_candidate_b"} else ""
        if scenario == "multi_signal_high_priority":
            duplicate_group = "DUP-V2-002"
        evaluation_rows.append({
            "work_id": work_id, "anomaly_label": bool(anomaly_types),
            "anomaly_types": "|".join(anomaly_types), "duplicate_group_id": duplicate_group,
            "label_usage_note": "EVALUATION ONLY — prohibited from production features, APIs, and scoring",
            "synthetic_demo_data": True,
        })

    # Force realistic paired works without adding any production helper label.
    for source_id, partner_id, description, group_id in (
        ("W-000707", "W-000708", "Construction of community drinking water tank beside central school campus", "DUP-V2-001"),
        ("W-001937", "W-001938", "Upgradation of rural approach road with culvert beside community school", "DUP-V2-002"),
    ):
        if source_id not in work_context or partner_id not in work_context:
            continue
        partner = work_context[source_id].copy()
        partner["work_id"] = partner_id
        partner["work_description"] = description
        partner_position = int(partner_id.split("-")[1]) - 1
        works[partner_position] = {key: partner[key] for key in works[partner_position]}
        work_context[partner_id] = partner
        evaluation_rows[partner_position]["duplicate_group_id"] = group_id

    for work in works:
        work_id = str(work["work_id"])
        context = work_context[work_id]
        lifecycle = str(work["lifecycle_stage"])
        scenario = context.get("scenario")
        sanctioned = float(work["sanctioned_amount_inr"] or 0)
        actual_start = date.fromisoformat(str(work["actual_start_date"])) if work["actual_start_date"] else None
        completion = date.fromisoformat(str(work["actual_completion_date"])) if work["actual_completion_date"] else None

        if sanctioned and actual_start:
            payment_count = 2 + (int(work_id[-3:]) % (5 if lifecycle == "COMPLETION" else 3))
            total_target = float(work["final_actual_expenditure_inr"] or work["current_expenditure_inr"])
            if scenario in {"fund_utilization_mismatch", "legacy_execution_demo"}:
                total_target = sanctioned * 1.58
            weights = [rng.uniform(0.5, 1.5) for _ in range(payment_count)]
            cumulative = 0
            payment_horizon = completion or AS_OF_DATE
            for stage, weight in enumerate(weights, 1):
                payment_index += 1
                amount = _money(total_target * weight / sum(weights))
                if stage == payment_count:
                    amount = max(0, int(round(total_target - cumulative)))
                request = actual_start + timedelta(days=stage * max(18, int((payment_horizon - actual_start).days / (payment_count + 1))))
                request = min(request, payment_horizon - timedelta(days=2))
                authorization = request + timedelta(days=rng.randint(1, 8))
                if (
                    scenario in {"payment_chronology_irregularity", "legacy_execution_demo", "multi_signal_high_priority"}
                    or context["generic_payment_chronology"]
                ) and stage == 1:
                    authorization = request - timedelta(days=1)
                release = max(authorization, request) + timedelta(days=rng.randint(1, 5))
                cumulative += amount
                payments.append({
                    "payment_id": f"PAY-V2-{payment_index:07d}", "work_id": work_id,
                    "payment_request_date": _iso(request), "authorization_date": _iso(authorization),
                    "payment_release_date": _iso(release), "payment_amount_inr": amount,
                    "payment_stage": stage, "invoice_number": f"INV-{work_id[2:]}-{stage:02d}",
                    "cumulative_expenditure_inr": cumulative, "payment_status": "RELEASED",
                    "authorized_by_agency_id": work["implementing_agency_id"],
                    "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
                })
                record_index += 1
                records.append({
                    "record_id": f"REC-V2-{record_index:08d}", "work_id": work_id,
                    "record_type": "PAYMENT_RELEASE", "status": "RECORDED", "record_date": _iso(release),
                    "evidence_id": f"PAY-V2-{payment_index:07d}", "source": "SYNTHETIC_PFMS_LIKE_HISTORY",
                    "applicable_lifecycle": "EXECUTION|COMPLETION", "expected_date": "",
                    "verification_status": "SYSTEM_RECORDED", "notes": "Synthetic payment history",
                    "synthetic_demo_data": True,
                })

            history_end = completion or AS_OF_DATE
            months = list(_month_starts(actual_start, history_end))
            for month_number, month in enumerate(months, 1):
                progress_index += 1
                fraction = month_number / max(len(months), 1)
                target = 100 if lifecycle == "COMPLETION" else float(work["current_physical_progress_pct"])
                physical = round(_clamp(target * fraction + rng.gauss(0, 2.2), 0, target), 1)
                if month_number == len(months):
                    physical = float(work["current_physical_progress_pct"])
                financial = round(_clamp(physical + rng.gauss(3 if context["overrun"] else 0, 8), 0, 170), 1)
                if scenario in {"fund_utilization_mismatch", "legacy_execution_demo"} or context["generic_fund_gap"]:
                    financial = round(_clamp(physical + 55 + month_number * 2, 0, 170), 1)
                report_date = min(month + timedelta(days=6 + index % 12), history_end)
                progress.append({
                    "progress_id": f"PROG-V2-{progress_index:08d}", "work_id": work_id,
                    "report_date": _iso(report_date), "physical_progress_pct": physical,
                    "financial_progress_pct": financial, "expected_progress_pct_by_date": round(_clamp(fraction * 100, 0, 100), 1),
                    "reported_status": "COMPLETED" if physical >= 100 else "ONGOING",
                    "reported_by_agency_id": work["implementing_agency_id"],
                    "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
                })
            record_index += 1
            records.append({
                "record_id": f"REC-V2-{record_index:08d}", "work_id": work_id,
                "record_type": "PROGRESS_REPORT", "status": "RECORDED", "record_date": _iso(history_end),
                "evidence_id": f"PROG-V2-{progress_index:08d}", "source": "SYNTHETIC_PROGRESS_HISTORY",
                "applicable_lifecycle": "EXECUTION|COMPLETION", "expected_date": "",
                "verification_status": "AGENCY_SUBMITTED", "notes": "Latest synthetic progress record",
                "synthetic_demo_data": True,
            })

        if work["sanction_date"]:
            record_index += 1
            records.append({
                "record_id": f"REC-V2-{record_index:08d}", "work_id": work_id,
                "record_type": "SANCTION_RECORD", "status": "RECORDED", "record_date": work["sanction_date"],
                "evidence_id": f"SAN-{work_id}", "source": "SYNTHETIC_SANCTION_REGISTER",
                "applicable_lifecycle": "EXECUTION|COMPLETION", "expected_date": "",
                "verification_status": "SYSTEM_RECORDED", "notes": "Synthetic sanction record",
                "synthetic_demo_data": True,
            })

        closure_types = [
            "COMPLETION_CERTIFICATE", "UTILIZATION_CERTIFICATE", "HANDOVER_RECORD",
            "PUBLIC_USE_EVIDENCE", "COMPLETED_WORK_PHOTO", "ASSET_REGISTER", "AUDIT_RECORD",
        ]
        if lifecycle == "COMPLETION" and completion:
            completeness = 0.94
            if scenario == "completed_missing_closure":
                completeness = 0.28
            elif scenario == "deterministic_compliance_issue":
                completeness = 0.45
            elif scenario in {"normal_work", "completed_full_closure"}:
                completeness = 1.0
            for offset, record_type in enumerate(closure_types, 1):
                exists = rng.random() < completeness
                if scenario == "deterministic_compliance_issue" and record_type == "ASSET_REGISTER":
                    exists = False
                if not exists:
                    continue
                record_index += 1
                record_date = completion + timedelta(days=offset + rng.randint(0, 45))
                records.append({
                    "record_id": f"REC-V2-{record_index:08d}", "work_id": work_id,
                    "record_type": record_type, "status": "RECORDED", "record_date": _iso(record_date),
                    "evidence_id": f"{record_type[:4]}-{work_id}", "source": "SYNTHETIC_CLOSURE_REGISTER",
                    "applicable_lifecycle": "COMPLETION", "expected_date": _iso(completion + timedelta(days=30)),
                    "verification_status": "DISTRICT_VERIFIED" if rng.random() < 0.8 else "PENDING_VERIFICATION",
                    "notes": "Synthetic closure evidence; not an official record", "synthetic_demo_data": True,
                })
                if record_type == "ASSET_REGISTER":
                    asset_index += 1
                    assets_rows.append({
                        "asset_id": f"ASSET-V2-{asset_index:07d}", "work_id": work_id,
                        "asset_type": work["sector"], "asset_register_status": "RECORDED",
                        "handover_status": "RECORDED" if completeness > 0.5 else "PENDING",
                        "public_use_status": "RECORDED" if completeness > 0.5 else "PENDING",
                        "audit_status": "VERIFIED" if completeness > 0.7 else "REQUIRES_REVIEW",
                        "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
                    })

        if actual_start:
            # Baseline evidence before execution.
            evidence_index += 1
            baseline_capture = actual_start - timedelta(days=2)
            asset = assets[evidence_index % len(assets)]
            geo_rows.append({
                "evidence_id": f"GEO-V2-{evidence_index:08d}", "work_id": work_id,
                "reporting_month": baseline_capture.strftime("%Y-%m"), "evidence_stage": "BEFORE_WORK",
                "capture_timestamp": f"{baseline_capture.isoformat()}T09:15:00+05:30",
                "upload_timestamp": f"{baseline_capture.isoformat()}T10:00:00+05:30",
                "latitude": work["registered_latitude"], "longitude": work["registered_longitude"],
                "physical_progress_pct": 0, "captured_by_user": f"IA-FIELD-{work_id[-4:]}",
                "captured_by_role": "IA", "implementing_agency_id": work["implementing_agency_id"],
                "source_type": "SEEDED_SYNTHETIC_DEMO_EVIDENCE", "image_path_or_object_id": asset["path"],
                "image_sha256": asset["sha256"], "verification_status": "DISTRICT_VERIFIED",
                "verified_by": f"DISTRICT-VERIFY-{work_id[-3:]}",
                "verification_timestamp": f"{baseline_capture.isoformat()}T15:00:00+05:30",
                "note": SYNTHETIC_NOTICE, "synthetic_demo_data": True,
            })

        if lifecycle == "EXECUTION" and actual_start:
            recent_months = list(_month_starts(max(actual_start, date(2026, 3, 1)), AS_OF_DATE))
            for month in recent_months:
                if (scenario == "missing_monthly_geo_evidence" or context["generic_geo_missing"]) and month == date(2026, 9, 1):
                    continue
                window = first_working_days(month.year, month.month)
                late = (scenario == "late_geo_evidence" or context["generic_geo_late"]) and month == date(2026, 8, 1)
                capture_day = window[-1] + timedelta(days=4) if late else window[min(index % 3, 2)]
                if month == date(2026, 9, 1) and capture_day > AS_OF_DATE:
                    continue
                evidence_index += 1
                asset = assets[evidence_index % len(assets)]
                capture_lat = float(work["registered_latitude"]) + rng.uniform(-0.0015, 0.0015)
                capture_lon = float(work["registered_longitude"]) + rng.uniform(-0.0015, 0.0015)
                if (scenario == "location_requires_review" or context["generic_location_review"]) and month == date(2026, 9, 1):
                    capture_lat += 0.025
                distance = haversine_metres(
                    float(work["registered_latitude"]), float(work["registered_longitude"]), capture_lat, capture_lon
                )
                geo_rows.append({
                    "evidence_id": f"GEO-V2-{evidence_index:08d}", "work_id": work_id,
                    "reporting_month": month.strftime("%Y-%m"), "evidence_stage": "MONTHLY_PROGRESS",
                    "capture_timestamp": f"{capture_day.isoformat()}T09:18:00+05:30",
                    "upload_timestamp": f"{capture_day.isoformat()}T10:02:00+05:30",
                    "latitude": round(capture_lat, 6), "longitude": round(capture_lon, 6),
                    "physical_progress_pct": work["current_physical_progress_pct"],
                    "captured_by_user": f"IA-FIELD-{work_id[-4:]}", "captured_by_role": "IA",
                    "implementing_agency_id": work["implementing_agency_id"],
                    "source_type": "SEEDED_SYNTHETIC_DEMO_EVIDENCE", "image_path_or_object_id": asset["path"],
                    "image_sha256": asset["sha256"],
                    "verification_status": "LOCATION_REQUIRES_REVIEW" if distance > 500 else "DISTRICT_VERIFIED",
                    "verified_by": "" if distance > 500 else f"DISTRICT-VERIFY-{work_id[-3:]}",
                    "verification_timestamp": "" if distance > 500 else f"{capture_day.isoformat()}T15:00:00+05:30",
                    "note": SYNTHETIC_NOTICE, "synthetic_demo_data": True,
                })

        if lifecycle == "COMPLETION" and completion:
            if scenario != "completed_missing_closure":
                evidence_index += 1
                asset = assets[evidence_index % len(assets)]
                capture = completion + timedelta(days=1)
                geo_rows.append({
                    "evidence_id": f"GEO-V2-{evidence_index:08d}", "work_id": work_id,
                    "reporting_month": capture.strftime("%Y-%m"), "evidence_stage": "COMPLETION",
                    "capture_timestamp": f"{capture.isoformat()}T11:10:00+05:30",
                    "upload_timestamp": f"{capture.isoformat()}T12:00:00+05:30",
                    "latitude": work["registered_latitude"], "longitude": work["registered_longitude"],
                    "physical_progress_pct": 100, "captured_by_user": f"IA-FIELD-{work_id[-4:]}",
                    "captured_by_role": "IA", "implementing_agency_id": work["implementing_agency_id"],
                    "source_type": "SEEDED_SYNTHETIC_DEMO_EVIDENCE", "image_path_or_object_id": asset["path"],
                    "image_sha256": asset["sha256"], "verification_status": "DISTRICT_VERIFIED",
                    "verified_by": f"DISTRICT-VERIFY-{work_id[-3:]}",
                    "verification_timestamp": f"{capture.isoformat()}T16:00:00+05:30",
                    "note": SYNTHETIC_NOTICE, "synthetic_demo_data": True,
                })

    allocation_rows: list[dict[str, Any]] = []
    works_by_mp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for work in works:
        works_by_mp[str(work["mp_id"])].append(work)
    for mp in mp_rows:
        for fy_index, financial_year in enumerate(("2024-25", "2025-26", "2026-27")):
            scoped = works_by_mp[str(mp["mp_id"])]
            factor = (0.82, 0.91, 1.0)[fy_index]
            sanctioned_total = sum(float(row["sanctioned_amount_inr"] or 0) for row in scoped) * factor / 3
            released_total = sanctioned_total * rng.uniform(0.78, 0.96)
            utilized_total = released_total * rng.uniform(0.72, 0.95)
            allocation_rows.append({
                "financial_year": financial_year, "state_name": mp["state_name"],
                "constituency": mp["constituency"], "mp_id": mp["mp_id"],
                "allocated_amount_inr": 50_000_000, "sanctioned_amount_inr": _money(sanctioned_total),
                "released_amount_inr": _money(released_total), "utilized_amount_inr": _money(utilized_total),
                "source_type": "SYNTHETIC_V2", "synthetic_demo_data": True,
            })

    files: list[tuple[str, list[dict[str, Any]], str]] = [
        ("01_mp_master.csv", mp_rows, "Synthetic MP and constituency scope master"),
        ("02_entities.csv", entity_rows, "Synthetic implementing-agency scope master"),
        ("03_works.csv", works, "One synthetic row per work"),
        ("04_payments.csv", payments, "Synthetic payment history kept one-to-many"),
        ("05_progress.csv", progress, "Synthetic monthly progress history kept one-to-many"),
        ("06_assets.csv", assets_rows, "Synthetic asset records; multiple rows per work supported"),
        ("10_work_records.csv", records, "Normalized synthetic records and certificates"),
        ("11_annual_allocations.csv", allocation_rows, "Synthetic historical annual fund aggregates"),
        ("12_geo_site_evidence.csv", geo_rows, "Clearly labelled synthetic geo-site evidence"),
        ("evaluation/anomaly_ground_truth_v2.csv", evaluation_rows, "Evaluation-only synthetic anomaly labels"),
    ]
    manifest_rows: list[dict[str, Any]] = []
    for filename, rows, purpose in files:
        path = output / filename
        _write_csv(path, rows)
        manifest_rows.append({
            "file_name": filename, "row_count": len(rows), "sha256": _sha256(path),
            "purpose": purpose, "synthetic_demo_data": True,
        })
    for asset in assets:
        manifest_rows.append({
            "file_name": asset["path"], "row_count": 0, "sha256": asset["sha256"],
            "purpose": "Clearly labelled seeded SVG prototype evidence", "synthetic_demo_data": True,
        })
    _write_csv(output / "00_manifest.csv", manifest_rows)
    metadata = {
        "dataset_profile": "demo_v2", "generated_at": GENERATED_AT, "random_seed": seed,
        "work_count": work_count, "as_of_date": AS_OF_DATE.isoformat(),
        "synthetic_demo_data": True, "disclaimer": SYNTHETIC_NOTICE,
        "scenario_parameters": {
            "states": len(STATES), "constituencies_per_state": 3,
            "districts_per_state": 3, "implementing_agencies_per_district": 3,
            "lifecycle_mix_rule": "10% pre-sanction, 35% execution, 55% completion before explicit cases",
            "geo_monthly_window": "first three Monday-Friday working days; no official holiday calendar",
            "location_review_threshold_metres": 500,
        },
        "representative_cases": REPRESENTATIVE_CASES,
        "ground_truth_path": "evaluation/anomaly_ground_truth_v2.csv",
        "ground_truth_usage": "evaluation only; prohibited from training features, serving, APIs, and review priority",
    }
    (output / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"output": str(output), "manifest": manifest_rows, **metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--work-count", type=int, default=WORK_COUNT)
    args = parser.parse_args()
    root = ProjectPaths.discover().project_root
    output = (args.output or root / "data" / "Demo-data-v2").resolve()
    if root not in output.parents:
        raise SystemExit("Refusing to generate outside the project root")
    result = generate(output, work_count=args.work_count)
    print(json.dumps({"output": result["output"], "work_count": result["work_count"], "files": len(result["manifest"])}, indent=2))


if __name__ == "__main__":
    main()
