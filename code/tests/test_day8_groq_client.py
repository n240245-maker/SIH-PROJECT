"""Mock-only Groq client contract, model preflight, and failure handling."""

from __future__ import annotations

import json

import httpx
import pytest

from rag.groq_client import (
    GroqAuthenticationError,
    GroqClient,
    GroqModelUnavailableError,
    GroqRateLimitError,
    GroqResponseError,
    GroqServerError,
    GroqSettings,
    GroqTimeoutError,
)
from rag.models import GroundedExplanation


def _valid_explanation() -> dict:
    return {
        "work_id": "W-000001",
        "summary": "Review evidence summary.",
        "why_flagged": [],
        "guideline_context": [],
        "verification_steps": ["Verify the source record."],
        "limitations": ["Human review is required."],
        "decision_statement": "The authorized reviewer decides any follow-up.",
    }


def _client(handler) -> GroqClient:
    return GroqClient(
        GroqSettings(
            groq_api_key="unit-test-secret",
            groq_model="openai/gpt-oss-120b",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_timeout_seconds=7,
        ),
        transport=httpx.MockTransport(handler),
    )


def test_groq_request_contract_and_structured_output():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(_valid_explanation())}}
                ]
            },
        )

    result = _client(handler).explain("system", "user")
    assert isinstance(result, GroundedExplanation)
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer unit-test-secret"
    body = captured["body"]
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["tool_choice"] == "none"
    assert "tools" not in body
    assert "store" not in body
    assert "browser_search" not in json.dumps(body)
    assert "web_search" not in json.dumps(body)
    assert body["response_format"]["type"] == "json_schema"
    schema = body["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert set(schema["schema"]["properties"]) == set(GroundedExplanation.model_fields)
    guideline_schema = schema["schema"]["$defs"]["GuidelineExplanation"]
    assert set(guideline_schema["required"]) == set(guideline_schema["properties"])


def test_request_local_identifier_constraints_are_in_schema():
    payload = _client(lambda request: httpx.Response(200)).request_payload(
        "system",
        "user",
        allowed_work_id="W-000001",
        allowed_evidence_codes=["EVIDENCE_A"],
        allowed_chunk_ids=["MPLADS-2023-P019"],
        allowed_clause_ids=["3.2.4"],
    )
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["work_id"]["const"] == "W-000001"
    assert schema["$defs"]["EvidenceExplanation"]["properties"][
        "source_evidence_codes"
    ]["items"]["enum"] == ["EVIDENCE_A"]
    guideline = schema["$defs"]["GuidelineExplanation"]["properties"]
    assert guideline["chunk_id"]["enum"] == ["MPLADS-2023-P019"]
    assert guideline["clause"]["enum"] == ["3.2.4", None]


def test_approved_model_access_preflight():
    client = _client(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "openai/gpt-oss-120b"}]}
        )
    )
    client.validate_configured_model()


def test_model_preflight_never_silently_substitutes():
    client = _client(
        lambda request: httpx.Response(200, json={"data": [{"id": "other/model"}]})
    )
    with pytest.raises(GroqModelUnavailableError, match="unavailable"):
        client.validate_configured_model()
    assert client.settings.groq_model == "openai/gpt-oss-120b"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, GroqAuthenticationError),
        (403, GroqAuthenticationError),
        (429, GroqRateLimitError),
        (500, GroqServerError),
    ],
)
def test_http_failures_are_typed(status, error):
    headers = {"retry-after": "12"} if status == 429 else None
    client = _client(
        lambda request: httpx.Response(
            status, headers=headers, json={"error": "test"}
        )
    )
    with pytest.raises(error) as caught:
        client.explain("system", "user")
    if status == 429:
        assert caught.value.retry_after == "12"


def test_timeout_is_typed():
    def timeout(request: httpx.Request):
        raise httpx.ReadTimeout("test timeout", request=request)

    with pytest.raises(GroqTimeoutError):
        _client(timeout).explain("system", "user")


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": "shape"},
        {"choices": [{"message": {"content": "not-json"}}]},
        {"choices": [{"message": {"content": json.dumps({"work_id": "W-000001"})}}]},
    ],
)
def test_malformed_or_schema_invalid_output_is_rejected(payload):
    client = _client(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(GroqResponseError):
        client.explain("system", "user")
