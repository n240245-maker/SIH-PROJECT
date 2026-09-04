"""Memory-bounded explanation serving from frozen Day-8.2 contexts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.repositories import ApplicationArtifactRepository
from rag.external_context import prepare_external_request
from rag.groq_client import GroqClient, GroqClientError, GroqResponseError
from rag.grounding import GroundingValidationError, validate_grounded_explanation
from rag.models import ExplanationResult, GroundedExplanation, RetrievedGuidelineChunk
from rag.prompt import PROMPT_VERSION, SYSTEM_PROMPT


class FrozenContextExplanationService:
    """Serve the governed context artifact without rebuilding its model inputs."""

    def __init__(
        self,
        artifacts: ApplicationArtifactRepository,
        llm_client: GroqClient,
    ) -> None:
        self.artifacts = artifacts
        self.llm_client = llm_client
        self._guideline_chunks = {
            str(chunk["chunk_id"]): chunk for chunk in artifacts.guideline_chunks
        }

    def _retrieved(
        self, context: dict[str, Any]
    ) -> list[RetrievedGuidelineChunk]:
        retrieved: list[RetrievedGuidelineChunk] = []
        for metadata in context["retrieval"]["chunks"]:
            chunk_id = str(metadata["chunk_id"])
            try:
                source = self._guideline_chunks[chunk_id]
            except KeyError:
                raise RuntimeError(
                    f"Frozen retrieval references unknown guideline chunk {chunk_id}"
                ) from None
            retrieved.append(
                RetrievedGuidelineChunk(
                    **metadata,
                    text=str(source["text"]),
                )
            )
        if not retrieved:
            raise RuntimeError("Frozen explanation context has no guideline retrieval")
        return retrieved

    def explain_work(
        self, work_id: str, *, use_llm: bool = False
    ) -> ExplanationResult:
        context = self.artifacts.explanations[work_id]
        bundle = context["evidence_bundle"]
        query = str(context["retrieval"]["query"])
        retrieved = self._retrieved(context)
        fallback = GroundedExplanation.model_validate(context["fallback_explanation"])
        direct = [str(item) for item in bundle["compliance"]["direct_chunk_ids"]]
        explanation = fallback
        mode = "DETERMINISTIC_FALLBACK"
        status = "OFFLINE_DEFAULT"
        issues: list[str] = []
        external_diagnostics: dict[str, object] = {}

        if use_llm:
            external = prepare_external_request(
                bundle,
                retrieved,
                query,
                self.llm_client.settings.groq_model,
            )
            external_diagnostics = dict(external.diagnostics)
            external_diagnostics.update(
                {
                    "http_outcome": "NOT_ATTEMPTED",
                    "schema_validation_outcome": "NOT_RUN",
                    "grounding_validation_outcome": "NOT_RUN",
                }
            )
            if not self.llm_client.settings.has_api_key:
                status = "SKIPPED_NO_GROQ_API_KEY"
                external_diagnostics["http_outcome"] = "SKIPPED_NO_API_KEY"
            elif not external.within_budget:
                status = "FALLBACK_EXTERNAL_CONTEXT_BUDGET"
                issues = [str(external.failure_reason)]
                external_diagnostics["http_outcome"] = "SKIPPED_LOCAL_BUDGET"
            else:
                try:
                    candidate = self.llm_client.explain(
                        SYSTEM_PROMPT,
                        external.user_prompt,
                        allowed_work_id=work_id,
                        allowed_evidence_codes=external.allowed_evidence_codes,
                        allowed_chunk_ids=external.allowed_guideline_chunk_ids,
                        allowed_clause_ids=external.allowed_clause_ids,
                    )
                    external_diagnostics["http_outcome"] = "HTTP_200"
                    external_diagnostics["schema_validation_outcome"] = "PASSED"
                    external_chunks = [
                        chunk
                        for chunk in retrieved
                        if chunk.chunk_id in external.allowed_guideline_chunk_ids
                    ]
                    validate_grounded_explanation(
                        candidate,
                        external.validation_bundle(work_id),
                        external_chunks,
                        allowed_clauses_by_chunk=external.allowed_clauses_by_chunk,
                    )
                    external_diagnostics["grounding_validation_outcome"] = "PASSED"
                    explanation = candidate
                    mode = "GROQ_GROUNDED"
                    status = "SUCCESS"
                except GroundingValidationError as exc:
                    status = "FALLBACK_GROUNDING_REJECTED"
                    issues = exc.issues
                    external_diagnostics["grounding_validation_outcome"] = "REJECTED"
                except GroqResponseError as exc:
                    status = f"FALLBACK_{type(exc).__name__.upper()}"
                    issues = [str(exc)]
                    external_diagnostics["http_outcome"] = (
                        f"HTTP_{exc.http_status}"
                        if exc.http_status is not None
                        else "HTTP_OUTCOME_UNKNOWN"
                    )
                    external_diagnostics["schema_validation_outcome"] = "REJECTED"
                except GroqClientError as exc:
                    status = f"FALLBACK_{type(exc).__name__.upper()}"
                    issues = [str(exc)]
                    external_diagnostics["http_outcome"] = (
                        f"HTTP_{exc.http_status}"
                        if exc.http_status is not None
                        else f"NO_HTTP_RESPONSE_{type(exc).__name__.upper()}"
                    )

        if mode == "DETERMINISTIC_FALLBACK":
            validate_grounded_explanation(fallback, bundle, retrieved)
        evidence_hash = hashlib.sha256(
            json.dumps(
                bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest().upper()
        expected_hash = str(
            context["explanation_metadata"].get("evidence_bundle_sha256", "")
        ).upper()
        if expected_hash and evidence_hash != expected_hash:
            raise RuntimeError("Frozen explanation evidence hash does not match metadata")

        return ExplanationResult(
            work_id=work_id,
            generation_mode=mode,
            provider="groq",
            model=self.llm_client.settings.groq_model,
            api_status=status,
            grounding_issues=issues,
            prompt_version=PROMPT_VERSION,
            guideline_version=str(retrieved[0].guideline_version),
            guideline_sha256=str(retrieved[0].guideline_sha256),
            evidence_bundle_sha256=evidence_hash,
            retrieved_chunk_ids=[item.chunk_id for item in retrieved],
            retrieval_query=query,
            direct_chunk_ids=direct,
            retrieved_guidelines=retrieved,
            evidence_bundle=bundle,
            explanation=explanation,
            external_request_diagnostics=external_diagnostics,
        )
