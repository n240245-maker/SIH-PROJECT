"""Application-facing explanation orchestration with fail-closed fallback."""

from __future__ import annotations

import hashlib
import json

from .evidence import ArtifactRepository
from .external_context import prepare_external_request
from .fallback import build_fallback_explanation
from .groq_client import GroqClient, GroqClientError, GroqResponseError
from .grounding import GroundingValidationError, validate_grounded_explanation
from .models import ExplanationResult
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_retrieval_query
from .retrieval import GuidelineRetriever


class ExplanationService:
    def __init__(
        self,
        repository: ArtifactRepository,
        retriever: GuidelineRetriever,
        llm_client: GroqClient,
    ) -> None:
        self.repository = repository
        self.retriever = retriever
        self.llm_client = llm_client

    def explain_work(self, work_id: str, *, use_llm: bool = False) -> ExplanationResult:
        bundle = self.repository.build_explanation_evidence(work_id)
        direct = bundle["compliance"]["direct_chunk_ids"]
        query = build_retrieval_query(bundle)
        retrieved = self.retriever.retrieve(query, direct_chunk_ids=direct)
        fallback = build_fallback_explanation(bundle, retrieved)
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

        # The local template must itself satisfy the same grounding contract.
        if mode == "DETERMINISTIC_FALLBACK":
            validate_grounded_explanation(fallback, bundle, retrieved)
        evidence_hash = hashlib.sha256(
            json.dumps(
                bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest().upper()
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
