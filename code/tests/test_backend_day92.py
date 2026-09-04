from __future__ import annotations

import re

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.presentation import (
    attention_level_from_band,
    financial_exceedance_display_severity,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as instance:
        yield instance


def _detail(client: TestClient, work_id: str) -> dict:
    response = client.get(f"/api/v1/works/{work_id}")
    assert response.status_code == 200
    return response.json()


def _docs(detail: dict) -> dict[str, dict]:
    return {row["key"]: row for row in detail["presentation"]["document_readiness"]["entries"]}


def test_attention_mapping_preserves_frozen_bands() -> None:
    assert attention_level_from_band("LOW", False) == "NORMAL"
    assert attention_level_from_band("LOW", True) == "LOW_ATTENTION"
    assert attention_level_from_band("MEDIUM", False) == "MEDIUM_ATTENTION"
    assert attention_level_from_band("HIGH", True) == "HIGH_ATTENTION"
    assert attention_level_from_band("CRITICAL", False) == "IMMEDIATE_PRIORITY"


def test_natural_distribution_is_complete_and_not_target_balanced(client: TestClient) -> None:
    body = client.get("/api/v1/dashboard/overview").json()
    assert body["attention_levels"] == {
        "NORMAL": 378, "LOW_ATTENTION": 189, "MEDIUM_ATTENTION": 1329,
        "HIGH_ATTENTION": 1096, "IMMEDIATE_PRIORITY": 8,
    }
    assert sum(body["attention_levels"].values()) == 3_000
    assert body["requires_review_count"] == 2_470
    assert body["immediate_priority_count"] == 8
    assert sorted(body["attention_level_percentages"].values()) != [0, 20, 20, 20, 40]


def test_queue_attention_and_review_filters(client: TestClient) -> None:
    normal = client.get("/api/v1/review-queue", params={"review_need": "ALL", "attention_level": "NORMAL"}).json()
    required = client.get("/api/v1/review-queue", params={"review_need": "REQUIRES_REVIEW"}).json()
    immediate = client.get("/api/v1/review-queue", params={"review_need": "IMMEDIATE_PRIORITY"}).json()
    assert normal["total"] == 378
    assert all(not row["requires_review"] for row in normal["items"])
    assert all(row["attention_level_label"] == "Normal" for row in normal["items"])
    assert required["total"] == 2_470
    assert immediate["total"] == 8
    assert all(row["attention_level"] == "IMMEDIATE_PRIORITY" for row in immediate["items"])


def test_execution_completion_documents_are_neutral(client: TestClient) -> None:
    detail = _detail(client, "W-002760")
    assert detail["profile"]["lifecycle_stage"] == "EXECUTION"
    docs = _docs(detail)
    for key in ("utilization_certificate", "handover", "public_use", "completed_work_photograph", "asset_register"):
        assert docs[key]["rule_result"] == "NOT_APPLICABLE"
        assert docs[key]["status_code"] == "EXPECTED_AFTER_COMPLETION"
        assert docs[key]["state"] == "not_applicable"


def test_completion_review_noncompliance_and_pass_are_exact(client: TestClient) -> None:
    reviewed = _docs(_detail(client, "W-001937"))
    assert reviewed["utilization_certificate"]["status_code"] == "REQUIRES_REVIEW"
    assert reviewed["completed_work_photograph"]["status_code"] == "RECORDED"
    noncompliant = _docs(_detail(client, "W-000933"))
    assert noncompliant["asset_register"]["status_code"] == "NON_COMPLIANT"
    assert noncompliant["handover"]["status_code"] == "RECORDED"


@pytest.mark.parametrize("pct,code", [(-1, "NORMAL"), (0, "NORMAL"), (0.1, "LOW_ATTENTION"), (5, "LOW_ATTENTION"), (5.1, "REQUIRES_REVIEW"), (15.1, "HIGH_ATTENTION"), (30.1, "VERY_HIGH_ATTENTION")])
def test_financial_presentation_magnitude(pct: float, code: str) -> None:
    assert financial_exceedance_display_severity(pct, observed=True)["code"] == code


def test_natural_small_and_large_exceedance_are_visually_distinct(client: TestClient) -> None:
    small = _detail(client, "W-001437")
    large = _detail(client, "W-002760")
    assert small["presentation"]["financial"]["exceedance_display_severity"]["code"] == "LOW_ATTENTION"
    assert small["presentation"]["financial"]["percentage_above_sanction"] == pytest.approx(0.0829187396)
    assert large["presentation"]["financial"]["exceedance_display_severity"]["code"] == "VERY_HIGH_ATTENTION"
    assert large["presentation"]["financial"]["percentage_above_sanction"] == pytest.approx(58.3162217659)


def test_friendly_warning_peer_trend_and_case_assessment(client: TestClient) -> None:
    detail = _detail(client, "W-002760")
    warnings = detail["presentation"]["warning_signals"]
    fund = next(row for row in warnings if row["technical_reference"]["alert_type"] == "FUND_PROGRESS_REVIEW")
    anomaly = next(row for row in warnings if row["technical_reference"]["alert_type"] == "STATISTICAL_ANOMALY")
    assert "percentage points" in fund["summary"] and "evidence=True" not in fund["summary"]
    assert "more statistically unusual than about" in anomaly["summary"]
    assert all("robust" not in row["comparison"].casefold() for row in detail["presentation"]["peer_comparisons"])
    assert "robust" not in detail["presentation"]["trend"]["assessment"].casefold()
    assessment = detail["presentation"]["case_assessment"]
    assert assessment["project"]["work_title"] == detail["profile"]["work_description"]
    assert assessment["financial_and_payment"]["sanctioned_amount_inr"] == 974_000
    assert assessment["verification_steps"]
    assert "wrongdoing" in assessment["review_note"]
    assert [row["dimension"] for row in detail["presentation"]["monitoring_health"]] == [
        "Finance", "Physical Progress", "Schedule", "Payments", "Compliance",
        "Duplicate Review", "Completion Records", "Evidence Availability",
    ]
    availability = detail["presentation"]["evidence_availability_rule"]
    assert availability["available_count"] <= availability["applicable_count"]
    assert "excluded" in availability["note"]


def test_alert_center_summary_preserves_actionable_semantics(client: TestClient) -> None:
    body = client.get("/api/v1/alerts", params={"limit": 1}).json()
    assert body["returned"] == 1
    assert body["summary"]
    by_type = {row["alert_type"]: row for row in body["summary"]}
    assert by_type["OBSERVED_OVER_SANCTION"]["category"] == "Financial"
    assert by_type["OBSERVED_OVER_SANCTION"]["actionable"] is True
    assert by_type["STATISTICAL_ANOMALY"]["status"] == "Analytical context"


def test_review_priority_is_bit_for_bit_unchanged(client: TestClient) -> None:
    detail = _detail(client, "W-001937")
    assert detail["priority"]["review_priority_score_0_100"] == pytest.approx(89.441901)
    assert detail["contribution_sum"] == pytest.approx(89.441901)


def test_pdf_has_lifecycle_states_and_never_calls_groq(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called():
        raise AssertionError("PDF must not call Groq")

    monkeypatch.setattr("backend.routers.explanations.get_explanation_service", fail_if_called)
    response = client.get("/api/v1/works/W-002760/case-report.pdf")
    assert response.status_code == 200
    with fitz.open(stream=response.content, filetype="pdf") as document:
        pdf_text = "\n".join(page.get_text() for page in document)
    assert "Expected after completion" in pdf_text
    assert re.search(r"handover missing", pdf_text, re.IGNORECASE) is None
    assert "GROQ_API_KEY" not in pdf_text and "gsk_" not in pdf_text


def test_contract_remains_ground_truth_free(client: TestClient) -> None:
    text = client.get("/api/v1/works/W-002760").text.casefold()
    assert "ground_truth" not in text
    assert "injected_anomaly" not in text
