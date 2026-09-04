"""Minimal direct HTTPS client for Groq Chat Completions structured output."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from intelligence.data.paths import ProjectPaths

from .models import GroundedExplanation


class GroqSettings(BaseSettings):
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.get_secret_value().strip())


def load_groq_settings(paths: ProjectPaths) -> GroqSettings:
    return GroqSettings(
        _env_file=paths.project_root / ".env",
        _env_file_encoding="utf-8",
    )


class GroqClientError(RuntimeError):
    """Base safe client failure."""

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class GroqTimeoutError(GroqClientError):
    pass


class GroqAuthenticationError(GroqClientError):
    pass


class GroqRateLimitError(GroqClientError):
    def __init__(self, retry_after: str | None = None) -> None:
        message = "Groq rate limit or quota was reached"
        if retry_after:
            message += f"; retry-after={retry_after}"
        super().__init__(message, http_status=429)
        self.retry_after = retry_after


class GroqServerError(GroqClientError):
    pass


class GroqResponseError(GroqClientError):
    pass


class GroqModelUnavailableError(GroqClientError):
    pass


class GroqClient:
    def __init__(
        self,
        settings: GroqSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def endpoint(self) -> str:
        return self.settings.groq_base_url.rstrip("/") + "/chat/completions"

    @property
    def models_endpoint(self) -> str:
        return self.settings.groq_base_url.rstrip("/") + "/models"

    def _headers(self) -> dict[str, str]:
        if not self.settings.has_api_key:
            raise GroqAuthenticationError("GROQ_API_KEY is not configured")
        return {
            "Authorization": (
                "Bearer " + self.settings.groq_api_key.get_secret_value().strip()
            ),
            "Content-Type": "application/json",
        }

    def request_payload(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        allowed_work_id: str | None = None,
        allowed_evidence_codes: list[str] | None = None,
        allowed_chunk_ids: list[str] | None = None,
        allowed_clause_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        schema = _provider_schema(
            allowed_work_id=allowed_work_id,
            allowed_evidence_codes=allowed_evidence_codes,
            allowed_chunk_ids=allowed_chunk_ids,
            allowed_clause_ids=allowed_clause_ids,
        )
        return {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "grounded_explanation",
                    "strict": True,
                    "schema": schema,
                },
            },
            # No tools are supplied. Explicitly prevent model-selected built-ins.
            "tool_choice": "none",
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            with httpx.Client(
                timeout=self.settings.groq_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.TimeoutException as exc:
            raise GroqTimeoutError("Groq request timed out") from exc
        except httpx.RequestError as exc:
            raise GroqClientError("Groq connection failed") from exc
        if response.status_code in {401, 403}:
            raise GroqAuthenticationError(
                "Groq rejected the configured credentials",
                http_status=response.status_code,
            )
        if response.status_code == 429:
            raise GroqRateLimitError(response.headers.get("retry-after"))
        if response.status_code >= 500:
            raise GroqServerError(
                f"Groq server returned HTTP {response.status_code}",
                http_status=response.status_code,
            )
        if response.status_code >= 400:
            raise GroqClientError(
                f"Groq returned HTTP {response.status_code}",
                http_status=response.status_code,
            )
        return response

    def validate_configured_model(self) -> None:
        """Fail closed when the approved model is unavailable to the account."""

        response = self._request("GET", self.models_endpoint)
        try:
            model_ids = {
                str(item["id"])
                for item in response.json().get("data", [])
                if isinstance(item, dict) and item.get("id")
            }
        except (ValueError, TypeError) as exc:
            raise GroqResponseError("Groq models response was malformed") from exc
        if self.settings.groq_model not in model_ids:
            raise GroqModelUnavailableError(
                f"Approved model {self.settings.groq_model!r} is unavailable to the configured account"
            )

    def explain(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        allowed_work_id: str | None = None,
        allowed_evidence_codes: list[str] | None = None,
        allowed_chunk_ids: list[str] | None = None,
        allowed_clause_ids: list[str] | None = None,
    ) -> GroundedExplanation:
        response = self._request(
            "POST",
            self.endpoint,
            json=self.request_payload(
                system_prompt,
                user_prompt,
                allowed_work_id=allowed_work_id,
                allowed_evidence_codes=allowed_evidence_codes,
                allowed_chunk_ids=allowed_chunk_ids,
                allowed_clause_ids=allowed_clause_ids,
            ),
        )
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty content")
            decoded = json.loads(content)
            return GroundedExplanation.model_validate(decoded)
        except (KeyError, IndexError, ValueError, TypeError, ValidationError) as exc:
            raise GroqResponseError(
                "Groq returned malformed or schema-invalid output",
                http_status=response.status_code,
            ) from exc


def _provider_schema(
    *,
    allowed_work_id: str | None,
    allowed_evidence_codes: list[str] | None,
    allowed_chunk_ids: list[str] | None,
    allowed_clause_ids: list[str] | None,
) -> dict[str, Any]:
    """Compact the schema and add request-local identifier constraints."""

    def compact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: compact(item)
                for key, item in value.items()
                if key not in {"title", "description"}
            }
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    schema = compact(deepcopy(GroundedExplanation.model_json_schema()))
    if allowed_work_id:
        schema["properties"]["work_id"]["const"] = allowed_work_id
    if allowed_evidence_codes:
        schema["$defs"]["EvidenceExplanation"]["properties"][
            "source_evidence_codes"
        ]["items"]["enum"] = list(dict.fromkeys(allowed_evidence_codes))
    if allowed_chunk_ids:
        schema["$defs"]["GuidelineExplanation"]["properties"]["chunk_id"][
            "enum"
        ] = list(dict.fromkeys(allowed_chunk_ids))
    if allowed_clause_ids:
        clause_schema = schema["$defs"]["GuidelineExplanation"]["properties"][
            "clause"
        ]
        clause_schema.clear()
        clause_schema["enum"] = [*dict.fromkeys(allowed_clause_ids), None]
    return schema


def serialized_request_size(payload: dict[str, Any]) -> int:
    """Match httpx's compact UTF-8 JSON serialization for a safe byte count."""

    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
