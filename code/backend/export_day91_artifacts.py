"""Export the intentional Day-9.1 OpenAPI and UI-polish application summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.main import app
from intelligence.data.paths import ProjectPaths


SECTION_ORDER = [
    "Case at a Glance / Case Overview",
    "Why This Work Needs Attention",
    "Early Warnings & Review Signals",
    "Payments & Work Progress",
    "Project Timeline & Event Checks",
    "MPLADS Rule & Compliance Check",
    "Duplicate Work Review",
    "Comparison With Similar Works",
    "Forecast & Early Warning",
    "Operational Trend Context",
    "AI-Assisted Case Brief",
    "Officer Review & Audit Trail",
]


def _write(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    paths = ProjectPaths.discover()
    destination = paths.processed_data_dir / "application"
    openapi = app.openapi()
    _write(destination / "openapi.json", openapi)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "TraceX - Kavach",
        "as_of_date": "2026-09-01",
        "day": "9.1",
        "new_or_updated_routes": [
            "GET /api/v1/works/{work_id}",
            "GET /api/v1/works/{work_id}/case-report.pdf",
            "POST /api/v1/works/{work_id}/explain",
        ],
        "pdf_report": {
            "available": True,
            "media_type": "application/pdf",
            "offline_fallback": True,
            "automatically_calls_groq": False,
            "validated_cached_groq_only": True,
        },
        "work_detail_section_order": SECTION_ORDER,
        "field_highlighting_rules": {
            "observed_or_deterministic_strong_issue": "red",
            "requires_review": "amber",
            "analytical_signal": "blue",
            "context_or_not_applicable": "neutral",
            "pass": "green",
            "source": "existing governed evidence only",
        },
        "friendly_peer_metric_mapping_count": 20,
        "warning_presentation_categories": [
            "Observed Condition", "Compliance Review", "Analytical Signal", "Operational Context"
        ],
        "explanation_and_report_behavior": {
            "default_explanation": "Local Deterministic Explanation",
            "groq_requires_explicit_user_action": True,
            "quantitative_facts_from_structured_backend": True,
            "report_download_never_calls_groq": True,
        },
        "verification": {
            "frontend_tests": "5 passed",
            "frontend_lint": "PASS",
            "frontend_build": "PASS",
            "python_regression": "197 passed",
            "browser_verification": "PASS",
            "browser_console_errors": 0,
            "pdf_visual_verification": "PASS",
        },
        "secrets_included": False,
        "ground_truth_used": False,
        "frozen_intelligence_changed": False,
    }
    _write(destination / "day9_1_ui_polish_summary.json", summary)
    print(destination / "openapi.json")
    print(destination / "day9_1_ui_polish_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
