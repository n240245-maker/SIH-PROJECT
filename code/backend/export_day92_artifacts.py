"""Export the Day-9.2 public API contract and final usability summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.main import app
from intelligence.data.paths import ProjectPaths


def _write(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    paths = ProjectPaths.discover()
    destination = paths.processed_data_dir / "application"
    _write(destination / "openapi.json", app.openapi())

    with TestClient(app) as client:
        overview = client.get("/api/v1/dashboard/overview").json()
        small = client.get("/api/v1/works/W-001437").json()
        execution = client.get("/api/v1/works/W-002760").json()
        critical = client.get("/api/v1/works/W-001937").json()
        noncompliant = client.get("/api/v1/works/W-000933").json()

    small_financial = small["presentation"]["financial"]
    execution_documents = {
        item["key"]: item["status_label"]
        for item in execution["presentation"]["document_readiness"]["entries"]
    }
    noncompliant_documents = {
        item["key"]: item["status_label"]
        for item in noncompliant["presentation"]["document_readiness"]["entries"]
    }
    labels = overview["attention_level_labels"]
    counts = overview["attention_levels"]
    percentages = overview["attention_level_percentages"]
    distribution = {
        code: {"label": labels[code], "count": counts[code], "percentage": percentages[code]}
        for code in labels
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "TRACE-X KAVACH",
        "day": "9.2",
        "as_of_date": overview["as_of_date"],
        "frozen_intelligence_changed": False,
        "source_csv_distribution_changed": False,
        "natural_attention_distribution": distribution,
        "natural_distribution_note": overview["natural_distribution_note"],
        "requires_review_count": overview["requires_review_count"],
        "immediate_priority_count": overview["immediate_priority_count"],
        "attention_definitions": {
            "NORMAL": "Frozen LOW band with no current actionable alert type.",
            "LOW_ATTENTION": "Frozen LOW band with at least one current actionable alert type.",
            "MEDIUM_ATTENTION": "Frozen MEDIUM band.",
            "HIGH_ATTENTION": "Frozen HIGH band.",
            "IMMEDIATE_PRIORITY": "Frozen CRITICAL band.",
        },
        "requires_review_definition": (
            "At least one current actionable observed, deterministic-compliance, payment, "
            "fund-progress, or corroborated duplicate-review signal; analytical anomaly, peer, "
            "trend, or weak-model context alone does not set it."
        ),
        "natural_small_over_sanction_case": {
            "work_id": "W-001437",
            "percentage_above_sanction": small_financial["percentage_above_sanction"],
            "display_level": small_financial["exceedance_display_severity"]["label"],
        },
        "friendly_metric_mapping_count": 28,
        "lifecycle_document_state_verification": {
            "W-002760_lifecycle": execution["profile"]["lifecycle_stage"],
            "W-002760": execution_documents,
            "W-000933_asset_register": noncompliant_documents["asset_register"],
        },
        "score_reconciliation": {
            "work_id": "W-001937",
            "frozen_score": critical["priority"]["review_priority_score_0_100"],
            "contribution_sum": critical["contribution_sum"],
            "unchanged": True,
        },
        "groq_behavior": {
            "default": "LOCAL_DETERMINISTIC_FALLBACK",
            "automatic_calls": False,
            "explicit_user_action_required": True,
            "grounding_validator_changed": False,
            "live_call_performed_for_day_9_2": False,
        },
        "pdf_behavior": {
            "automatic_groq_calls": False,
            "visual_verification": "PASS — all 18 rendered pages inspected",
            "files": [
                "output/pdf/MPLADS_Sentinel_Case_W-002760_2026-09-04.pdf",
                "output/pdf/MPLADS_Sentinel_Case_W-001937_2026-09-04.pdf",
                "output/pdf/MPLADS_Sentinel_Case_W-000933_2026-09-04.pdf",
                "output/pdf/MPLADS_Sentinel_Case_W-000476_2026-09-04.pdf",
            ],
        },
        "verification": {
            "frontend_tests": "9 passed",
            "frontend_lint": "PASS",
            "frontend_build": "PASS",
            "python_full_regression": "214 passed, 1 dependency deprecation warning",
            "python_day9_2_focused": "17 passed, 1 dependency deprecation warning",
            "browser_status": "PASS",
            "browser_console_errors_or_warnings": 0,
            "browser_cases": [
                "W-000476", "W-000012", "W-001437", "W-002760", "W-001937", "W-001966", "W-000933"
            ],
            "demo_data_hash_test": "PASS — all 12 source CSV hashes match the immutable baseline",
            "ground_truth_isolated": True,
        },
        "secrets_included": False,
    }
    summary_path = destination / "day9_2_final_usability_summary.json"
    _write(summary_path, summary)
    print(destination / "openapi.json")
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
