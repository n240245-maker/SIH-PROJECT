"""Day-8 offline-first artifact runner and optional bounded Groq smoke check."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from intelligence.data.paths import ProjectPaths

from .evidence import ArtifactRepository
from .external_context import DAY81_SMOKE_BASELINE
from .fallback import build_fallback_explanation
from .groq_client import (
    GroqClient,
    GroqClientError,
    GroqModelUnavailableError,
    load_groq_settings,
)
from .models import GroundedExplanation, RetrievedGuidelineChunk
from .prompt import PROMPT_VERSION, build_retrieval_query
from .retrieval import DEFAULT_CONTEXT_CAP, DEFAULT_TOP_K, GuidelineRetriever
from .service import ExplanationService


DAY8_OUTPUTS = {
    "data/processed/guideline_embeddings.npy",
    "data/processed/guideline_embedding_metadata.json",
    "data/processed/rag_retrieval_audit.json",
    "data/processed/explanation_context.jsonl",
    "data/processed/day8_rag_summary.json",
    "data/processed/evaluation/day8_grok_live_smoke.json",
    "data/processed/evaluation/day8_groq_live_smoke.json",
    "data/processed/evaluation/day8_2_payload_diagnostics.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _relative(paths: ProjectPaths, path: Path) -> str:
    return path.relative_to(paths.project_root).as_posix()


def prior_artifact_hashes(paths: ProjectPaths) -> dict[str, str]:
    candidates = list(paths.processed_data_dir.rglob("*"))
    candidates.extend(path for path in paths.models_dir.rglob("*") if path.is_file())
    return {
        _relative(paths, path): _sha256(path)
        for path in candidates
        if path.is_file() and _relative(paths, path) not in DAY8_OUTPUTS
    }


def demo_hashes(paths: ProjectPaths) -> dict[str, str]:
    return {
        path.name: _sha256(path)
        for path in sorted(paths.demo_data_dir.glob("*.csv"))
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _context_record(
    bundle: dict[str, Any],
    query: str,
    retrieved: list[RetrievedGuidelineChunk],
    fallback: GroundedExplanation,
    configured_model: str,
) -> dict[str, Any]:
    evidence_hash = hashlib.sha256(
        json.dumps(
            bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest().upper()
    return {
        "work_id": bundle["work_id"],
        "explanation_metadata": {
            "explanation_mode": "DETERMINISTIC_FALLBACK",
            "provider": "groq",
            "model": configured_model,
            "prompt_version": PROMPT_VERSION,
            "guideline_version": retrieved[0].guideline_version,
            "guideline_sha256": retrieved[0].guideline_sha256,
            "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieved],
            "evidence_bundle_sha256": evidence_hash,
        },
        "evidence_bundle": bundle,
        "retrieval": {
            "query": query,
            "query_source": "MINIMIZED_STRUCTURED_EVIDENCE",
            "semantic_top_k": DEFAULT_TOP_K,
            "chunks": [chunk.metadata() for chunk in retrieved],
        },
        "fallback_explanation": fallback.model_dump(mode="json"),
    }


def _audit_case_indices(bundles: list[dict[str, Any]]) -> list[tuple[str, int]]:
    cases: list[tuple[str, int]] = []
    compliance = [
        index
        for index, bundle in enumerate(bundles)
        if bundle["compliance"]["direct_chunk_ids"]
    ][:5]
    cases.extend(("COMPLIANCE", index) for index in compliance)
    used = set(compliance)
    predicates = {
        "DUPLICATE": lambda bundle: bool(
            bundle["duplicate"]["review_candidates_only"]
        ),
        "PAYMENT_EXECUTION": lambda bundle: bool(
            bundle["payment_execution"]["selected_evidence"]
        ),
        "COST_OVERRUN_WARNING": lambda bundle: bundle["prediction"].get(
            "cost_overrun_serving_score"
        )
        is not None,
        "TREND_CONTEXT": lambda bundle: bool(
            bundle["trend"].get("operational_trend_deviation_flag")
        ),
    }
    for category, predicate in predicates.items():
        index = next(
            i
            for i, bundle in enumerate(bundles)
            if i not in used and predicate(bundle)
        )
        cases.append((category, index))
        used.add(index)
    return cases


def _retrieval_audit(
    bundles: list[dict[str, Any]],
    queries: list[str],
    retrieved_sets: list[list[RetrievedGuidelineChunk]],
) -> dict[str, Any]:
    cases = []
    direct_test_count = 0
    for category, index in _audit_case_indices(bundles):
        bundle = bundles[index]
        direct = set(bundle["compliance"]["direct_chunk_ids"])
        retrieved_ids = {item.chunk_id for item in retrieved_sets[index]}
        if category == "COMPLIANCE":
            direct_test_count += len(direct)
        cases.append(
            {
                "category": category,
                "work_id": bundle["work_id"],
                "query": queries[index],
                "direct_chunk_ids": sorted(direct),
                "direct_references_retained": direct.issubset(retrieved_ids),
                "results": [item.metadata() for item in retrieved_sets[index]],
            }
        )
    if not all(
        case["direct_references_retained"]
        for case in cases
        if case["category"] == "COMPLIANCE"
    ):
        raise RuntimeError("A direct compliance reference was displaced")
    return {
        "retrieval_policy": "all unique direct rule chunks, then up to five semantic chunks",
        "semantic_top_k": DEFAULT_TOP_K,
        "context_cap": DEFAULT_CONTEXT_CAP,
        "direct_compliance_references_tested": direct_test_count,
        "representative_cases": cases,
    }


def _write_live_smoke(
    paths: ProjectPaths,
    service: ExplanationService,
    selected_work_ids: list[str],
    *,
    explicit_live_smoke: bool,
) -> dict[str, Any]:
    evaluation = paths.processed_data_dir / "evaluation"
    evaluation.mkdir(parents=True, exist_ok=True)
    destination = evaluation / "day8_groq_live_smoke.json"
    diagnostics_destination = evaluation / "day8_2_payload_diagnostics.json"
    settings = service.llm_client.settings
    if not settings.has_api_key:
        payload = {
            "status": "SKIPPED_NO_GROQ_API_KEY",
            "explicit_live_smoke": explicit_live_smoke,
            "calls_attempted": 0,
            "results": [],
        }
    elif not explicit_live_smoke:
        payload = {
            "status": "SKIPPED_NOT_EXPLICITLY_REQUESTED",
            "explicit_live_smoke": False,
            "calls_attempted": 0,
            "results": [],
        }
    else:
        try:
            service.llm_client.validate_configured_model()
        except GroqModelUnavailableError:
            raise
        except GroqClientError as exc:
            payload = {
                "status": f"FALLBACK_MODEL_PREFLIGHT_{type(exc).__name__.upper()}",
                "explicit_live_smoke": True,
                "calls_attempted": 0,
                "results": [],
                "safe_error": str(exc),
            }
            _write_json(destination, payload)
            return payload
        results = []
        safe_case_diagnostics = []
        for work_id in selected_work_ids:
            result = service.explain_work(work_id, use_llm=True)
            diagnostics = result.external_request_diagnostics
            safe_case_diagnostics.append(
                {
                    "work_id": work_id,
                    **diagnostics,
                    "final_explanation_mode": result.generation_mode,
                    "api_status": result.api_status,
                    "grounding_issues": result.grounding_issues,
                }
            )
            results.append(
                {
                    "work_id": work_id,
                    "provider": result.provider,
                    "model": result.model,
                    "generation_mode": result.generation_mode,
                    "api_status": result.api_status,
                    "request_size_bytes": diagnostics.get("request_json_bytes"),
                    "evidence_item_count": diagnostics.get("evidence_item_count"),
                    "guideline_excerpt_count": diagnostics.get(
                        "guideline_excerpt_count"
                    ),
                    "direct_chunk_count": diagnostics.get("direct_chunk_count"),
                    "semantic_chunk_count": diagnostics.get(
                        "semantic_chunk_count"
                    ),
                    "http_outcome": diagnostics.get("http_outcome"),
                    "schema_validation_outcome": diagnostics.get(
                        "schema_validation_outcome"
                    ),
                    "grounding_validation_outcome": diagnostics.get(
                        "grounding_validation_outcome"
                    ),
                    "grounding_issues": result.grounding_issues,
                    "explanation": result.explanation.model_dump(mode="json"),
                }
            )
        calls_attempted = sum(
            str(item["http_outcome"]).startswith("HTTP_")
            or str(item["http_outcome"]).startswith("NO_HTTP_RESPONSE_")
            for item in results
        )
        payload = {
            "status": (
                "COMPLETED"
                if all(item["api_status"] == "SUCCESS" for item in results)
                else "COMPLETED_WITH_FALLBACK"
            ),
            "explicit_live_smoke": True,
            "cases_evaluated": len(results),
            "calls_attempted": calls_attempted,
            "results": results,
        }
        safe_diagnostics = {
            "status": payload["status"],
            "day8_1_failure_analysis": {
                "http_413_cases": ["W-001937", "W-001966"],
                "grounding_rejected_case": "W-002240",
                "grounding_rejection_reasons": [
                    "UNSUPPORTED_CLAUSE:MPLADS-2023-P019:3.2.4; 3.2.6",
                    "INVENTED_COMPLIANCE_RULE:['MPLADS-3.2.4']",
                ],
            },
            "day8_1_original_requests": [
                {"work_id": work_id, **DAY81_SMOKE_BASELINE[work_id]}
                for work_id in selected_work_ids
            ],
            "day8_2_minimized_requests": [
                item for item in safe_case_diagnostics
            ],
            "credential_fields_logged": False,
        }
        _write_json(diagnostics_destination, safe_diagnostics)
    _write_json(destination, payload)
    return payload


def run_day8(
    paths: ProjectPaths,
    *,
    live_smoke: bool = False,
    live_smoke_limit: int = 3,
) -> dict[str, Any]:
    if not 1 <= live_smoke_limit <= 3:
        raise ValueError("Live smoke limit must be between 1 and 3")
    frozen_before = prior_artifact_hashes(paths)
    demo_before = demo_hashes(paths)
    if len(demo_before) != 12:
        raise ValueError(f"Expected 12 Demo-data CSV files, found {len(demo_before)}")

    repository = ArtifactRepository(paths)
    retriever = GuidelineRetriever(paths)
    settings = load_groq_settings(paths)
    service = ExplanationService(repository, retriever, GroqClient(settings))

    bundles = [
        repository.build_explanation_evidence(work_id)
        for work_id in repository.work_ids
    ]
    if len(bundles) != 3_000:
        raise RuntimeError("Day-8 context requires exactly 3,000 work records")
    queries = [build_retrieval_query(bundle) for bundle in bundles]
    direct_sets = [bundle["compliance"]["direct_chunk_ids"] for bundle in bundles]
    retrieved_sets = retriever.retrieve_many(queries, direct_sets)
    fallbacks = [
        build_fallback_explanation(bundle, retrieved)
        for bundle, retrieved in zip(bundles, retrieved_sets, strict=True)
    ]

    context_path = paths.processed_data_dir / "explanation_context.jsonl"
    with context_path.open("w", encoding="utf-8", newline="\n") as stream:
        for bundle, query, retrieved, fallback in zip(
            bundles, queries, retrieved_sets, fallbacks, strict=True
        ):
            stream.write(
                json.dumps(
                    _context_record(
                        bundle, query, retrieved, fallback, settings.groq_model
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

    audit = _retrieval_audit(bundles, queries, retrieved_sets)
    _write_json(paths.processed_data_dir / "rag_retrieval_audit.json", audit)
    smoke_indices = [index for _, index in _audit_case_indices(bundles)]
    smoke_work_ids = list(
        dict.fromkeys(bundles[index]["work_id"] for index in smoke_indices)
    )[:live_smoke_limit]
    smoke = _write_live_smoke(
        paths,
        service,
        smoke_work_ids,
        explicit_live_smoke=live_smoke,
    )

    frozen_after = prior_artifact_hashes(paths)
    demo_after = demo_hashes(paths)
    if frozen_before != frozen_after:
        changed = sorted(
            name
            for name in set(frozen_before) | set(frozen_after)
            if frozen_before.get(name) != frozen_after.get(name)
        )
        raise RuntimeError(f"Day 8 changed prior artifacts: {changed}")
    if demo_before != demo_after:
        raise RuntimeError("Day 8 changed Demo-data")

    direct_counts = [len(items) for items in direct_sets]
    unique_direct = sorted({item for items in direct_sets for item in items})
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "guideline_version": retriever.chunks[0]["guideline_version"],
        "guideline_sha256": retriever.metadata["guideline_sha256"],
        "chunk_count": retriever.metadata["chunk_count"],
        "embedding_model": retriever.metadata["embedding_model"],
        "embedding_dimension": retriever.metadata["embedding_dimension"],
        "retrieval_policy": audit["retrieval_policy"],
        "direct_reference_count_statistics": {
            "works_with_direct_references": sum(count > 0 for count in direct_counts),
            "total_work_chunk_references": sum(direct_counts),
            "unique_direct_chunk_ids": unique_direct,
            "retrieval_audit_references_tested": audit[
                "direct_compliance_references_tested"
            ],
        },
        "semantic_retrieval_top_k": DEFAULT_TOP_K,
        "maximum_context_chunks": DEFAULT_CONTEXT_CAP,
        "prompt_version": PROMPT_VERSION,
        "llm_provider": "groq",
        "configured_model": settings.groq_model,
        "api_base": settings.groq_base_url,
        "api_endpoint": "/chat/completions",
        "external_tools_enabled": False,
        "web_search_enabled": False,
        "x_search_enabled": False,
        "live_smoke_status": smoke["status"],
        "fallback_available": True,
        "explanation_context_count": len(bundles),
        "structured_output_schema_fields": list(
            GroundedExplanation.model_fields.keys()
        ),
        "representative_fallback": fallbacks[0].model_dump(mode="json"),
        "artifact_paths": {
            "guideline_embeddings": "data/processed/guideline_embeddings.npy",
            "embedding_metadata": "data/processed/guideline_embedding_metadata.json",
            "retrieval_audit": "data/processed/rag_retrieval_audit.json",
            "explanation_context": "data/processed/explanation_context.jsonl",
            "live_smoke": "data/processed/evaluation/day8_groq_live_smoke.json",
        },
        "integrity": {
            "prior_artifact_count_verified": len(frozen_before),
            "prior_artifacts_unchanged": True,
            "demo_data_file_count": len(demo_before),
            "demo_data_hashes_unchanged": True,
        },
        "governance_statement": (
            "The Groq-hosted model explains supplied evidence only and never recalculates risk, "
            "detects wrongdoing, decides compliance, or overrides deterministic rules."
        ),
        "ground_truth_used": False,
    }
    _write_json(paths.processed_data_dir / "day8_rag_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-smoke", action="store_true")
    parser.add_argument("--live-smoke-limit", type=int, default=3)
    args = parser.parse_args()
    summary = run_day8(
        ProjectPaths.discover(),
        live_smoke=args.live_smoke,
        live_smoke_limit=args.live_smoke_limit,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
