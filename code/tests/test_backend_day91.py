from __future__ import annotations

import math
import re

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_artifacts, get_validated_explanation_cache
from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as instance:
        yield instance


def _pdf_text(content: bytes) -> str:
    with fitz.open(stream=content, filetype="pdf") as document:
        return "\n".join(page.get_text() for page in document)


def test_day91_presentation_preserves_score_and_safe_display_calculations(client: TestClient) -> None:
    body = client.get("/api/v1/works/W-002760").json()
    financial = body["presentation"]["financial"]
    assert financial["released_minus_sanction_inr"] == 568_000
    assert financial["percentage_above_sanction"] == pytest.approx(58.31622176591375)
    assert financial["financial_minus_physical_gap_percentage_points"] == pytest.approx(129.4)
    assert financial["released_exceeds_visible_sanction"] is True
    assert body["presentation"]["payment_chronology"] == {
        "authorization_before_request": True,
        "authorization_date": "2026-08-08",
        "request_date": "2026-08-09",
    }
    critical = client.get("/api/v1/works/W-001937").json()
    assert critical["contribution_sum"] == pytest.approx(89.441901)
    assert critical["priority"]["review_priority_score_0_100"] == pytest.approx(89.441901)


def test_field_highlights_are_governed_and_semantically_distinct(client: TestClient) -> None:
    high = client.get("/api/v1/works/W-002760").json()["presentation"]["highlighted_fields"]
    assert high["released_payment_total_inr_as_of"]["state"] == "strong_issue"
    assert high["financial_minus_physical_gap_pct_as_of"]["state"] == "review"
    non_compliant = client.get("/api/v1/works/W-000933").json()
    assert non_compliant["presentation"]["highlighted_fields"]["asset_record_count_as_of"]["state"] == "strong_issue"
    compliance = non_compliant["compliance"]["rules"]
    assert any(item["result"] == "NON_COMPLIANT" for item in compliance)
    assert any(item["result"] == "REVIEW" for item in compliance)
    low = client.get("/api/v1/works/W-000476").json()
    assert low["priority"]["review_priority_band"] == "LOW"
    assert "released_payment_total_inr_as_of" not in low["presentation"]["highlighted_fields"]
    critical_signals = client.get("/api/v1/works/W-001937").json()["presentation"]["warning_signals"]
    anomaly = next(item for item in critical_signals if item["technical_reference"]["alert_type"] == "STATISTICAL_ANOMALY")
    assert anomaly["category"] == "Analytical Signal"
    assert anomaly["state"] == "analytical"


def test_timeline_flags_only_existing_governed_conditions(client: TestClient) -> None:
    detailed = client.get("/api/v1/works/W-002760").json()
    timeline = detailed["presentation"]["timeline"]
    flagged = {item["label"] for item in timeline["events"] if item["state"] in {"review", "strong_issue"}}
    assert flagged == {
        "Sanction", "Payment authorization", "Payment request",
        "Last payment release", "Latest progress report",
    }
    low = client.get("/api/v1/works/W-000476").json()["presentation"]["timeline"]
    assert low["attention_count"] == 0
    assert all(item["state"] in {"recorded", "planned"} for item in low["events"])


def test_case_report_unknown_work_is_safe_404(client: TestClient) -> None:
    response = client.get("/api/v1/works/W-NOT-REAL/case-report.pdf")
    assert response.status_code == 404
    assert response.json() == {"detail": "Work was not found"}


def test_case_report_is_valid_nonempty_pdf_with_required_governance(client: TestClient) -> None:
    get_validated_explanation_cache().clear()
    response = client.get("/api/v1/works/W-001937/case-report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "TraceX_Kavach_Case_W-001937_" in response.headers["content-disposition"]
    assert "MPLADS_Sentinel" not in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 5_000
    text = _pdf_text(response.content)
    assert "W-001937" in text
    assert "Review Priority" in text
    assert "MPLADS Monitoring & Management Platform" in text
    assert "authorized human verification required" in text
    assert "DETERMINISTIC_FALLBACK" not in text
    assert "GROQ_API_KEY" not in text
    assert "gsk_" not in text
    assert "SELECTED:semantic" not in text
    assert re.search(r"\bnan\b", text, flags=re.IGNORECASE) is None
    high_text = _pdf_text(client.get("/api/v1/works/W-002760/case-report.pdf").content)
    assert "129.416" not in high_text
    assert "Observed overdue=" not in high_text


def test_report_generation_never_calls_groq(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called():
        raise AssertionError("case report must never call Groq")

    monkeypatch.setattr("backend.routers.explanations.get_explanation_service", fail_if_called)
    response = client.get("/api/v1/works/W-002760/case-report.pdf")
    assert response.status_code == 200


def test_report_uses_only_already_validated_cached_groq_output(client: TestClient) -> None:
    cache = get_validated_explanation_cache()
    artifacts = get_artifacts()
    cache.clear()
    cache.put("W-001937", artifacts, {
        "work_id": "W-001937",
        "generation_mode": "GROQ_GROUNDED",
        "api_status": "SUCCESS",
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "explanation": {
            "summary": "Validated cached narrative for report verification.",
            "why_flagged": [],
            "decision_statement": "Authorized human verification remains required.",
        },
        "retrieved_guidelines": [],
        "fallback_used": False,
    })
    try:
        text = _pdf_text(client.get("/api/v1/works/W-001937/case-report.pdf").content)
        assert "GROQ_GROUNDED" not in text
        assert "Validated cached narrative" in text
    finally:
        cache.clear()


def test_day91_contract_and_payload_remain_ground_truth_free(client: TestClient) -> None:
    openapi = client.get("/openapi.json")
    assert "/api/v1/works/{work_id}/case-report.pdf" in openapi.json()["paths"]
    detail = client.get("/api/v1/works/W-002760").text.casefold()
    assert "ground_truth" not in detail
    assert "injected_anomaly" not in detail
    assert "duplicate_group_reference" not in detail
    assert math.isfinite(client.get("/api/v1/works/W-002760").json()["contribution_sum"])
