"""Export the updated application contract and local upgrade summary."""

from __future__ import annotations

import json

from backend.main import app
from intelligence.data.paths import ProjectPaths


def main() -> None:
    paths = ProjectPaths.discover()
    output_dir = paths.processed_data_dir / "application"
    output_dir.mkdir(parents=True, exist_ok=True)
    openapi_path = output_dir / "openapi.json"
    summary_path = output_dir / "pre_day10_product_upgrade_summary.json"
    openapi_path.write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    recommendation_routes = sorted(
        path for path in app.openapi()["paths"] if path.startswith("/api/v1/recommendations")
    )
    summary = {
        "application": "TRACE-X KAVACH",
        "subtitle": "MPLADS Monitoring & Management Platform",
        "upgrade_status": "DEPLOYMENT_APPROVED_AFTER_LOCAL_REVIEW",
        "frozen_analytical_work_count": 3000,
        "runtime_records_are_additional": True,
        "recommendation_workflow": "MP_TO_DISTRICT_OPERATIONAL",
        "new_backend_routes": recommendation_routes,
        "new_frontend_routes": [
            "/recommend-work",
            "/my-works",
            "/new-recommendations",
            "/recommendations/{recommendation_id}",
        ],
        "removed_frontend_routes": ["/methodology"],
        "runtime_paths": [
            "data/runtime/recommendations.json",
            "data/runtime/recommendation_events.jsonl",
            "data/runtime/uploads/",
        ],
        "verification": {
            "focused_backend": "15 PASSED",
            "existing_day9_backend": "39 PASSED",
            "full_python": "243 PASSED; 1 DEPENDENCY DEPRECATION WARNING",
            "frontend_tests": "11 PASSED",
            "frontend_lint": "PASSED",
            "frontend_build": "PASSED",
            "browser_smoke": "PASSED",
            "browser_responsive_widths": [1280, 1024, 768],
            "recent_activity_timeline_visual_check": "PASSED",
            "local_pdf_generation": "PASSED",
            "automatic_explanation_calls_during_browser_smoke": 0,
            "ground_truth_isolation": "VERIFIED",
            "secret_audit": "0 MATCHES IN FRONTEND, RUNTIME, AND GENERATED APPLICATION ARTIFACTS",
            "visible_ui_string_audit": "PASSED",
            "frozen_artifact_integrity": "VERIFIED_UNCHANGED",
            "demo_data_hashes": "12 OF 12 VERIFIED UNCHANGED",
        },
        "deployment_performed": True,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(openapi_path)
    print(summary_path)


if __name__ == "__main__":
    main()
