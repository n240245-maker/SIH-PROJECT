"""Generate local duplicate-work embeddings and candidate-review artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import sentence_transformers
from sentence_transformers import SentenceTransformer

from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths

from .detector import (
    DUPLICATE_CANDIDATE_THRESHOLD,
    DUPLICATE_SCORE_WEIGHTS,
    REVIEW_MAX_DATE_DIFFERENCE_DAYS,
    REVIEW_MAX_DISTANCE_KM,
    REVIEW_MIN_AMOUNT_SIMILARITY,
    REVIEW_MIN_SCORE,
    REVIEW_MIN_TEXT_SIMILARITY,
    build_duplicate_candidates,
)
from .similarity import TOP_NEIGHBORS_PER_WORK, retrieve_cosine_candidate_pairs
from .text import build_duplicate_search_text


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True, slots=True)
class DuplicateArtifacts:
    embeddings: Path
    embedding_metadata: Path
    candidates: Path
    summary: Path


def _text_contract_hash(work_ids: list[str], texts: list[str]) -> str:
    digest = hashlib.sha256()
    for work_id, text in zip(work_ids, texts, strict=True):
        digest.update(work_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _series_percentile(series: pd.Series, percentile: float) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return None if numeric.empty else float(numeric.quantile(percentile))


def _structured_evidence_audit(candidates: pd.DataFrame) -> dict[str, Any]:
    audit: dict[str, Any] = {}
    for threshold in (85.0, 90.0, 92.5, 95.0):
        rows = candidates.loc[
            candidates["duplicate_similarity_score_0_100"].ge(threshold)
        ]
        key = f"score_at_or_above_{threshold:g}"
        audit[key] = {
            "pair_count": int(len(rows)),
            "text_similarity_median": _series_percentile(
                rows["text_cosine_similarity"], 0.50
            ),
            "text_similarity_p90": _series_percentile(
                rows["text_cosine_similarity"], 0.90
            ),
            "distance_km_median": _series_percentile(
                rows["geographic_distance_km"], 0.50
            ),
            "distance_km_p90": _series_percentile(
                rows["geographic_distance_km"], 0.90
            ),
            "amount_similarity_p10": _series_percentile(
                rows["amount_similarity"], 0.10
            ),
            "amount_similarity_median": _series_percentile(
                rows["amount_similarity"], 0.50
            ),
            "date_difference_days_median": _series_percentile(
                rows["recommendation_date_difference_days"], 0.50
            ),
            "date_difference_days_p90": _series_percentile(
                rows["recommendation_date_difference_days"], 0.90
            ),
            "same_district_pct": float(100.0 * rows["same_district"].mean()),
            "same_block_pct": float(100.0 * rows["same_block"].mean()),
            "same_village_pct": float(100.0 * rows["same_village"].mean()),
            "sector_match_pct": float(100.0 * rows["sector_match"].mean()),
            "sub_sector_match_pct": float(
                100.0 * rows["sub_sector_match"].mean()
            ),
            "implementing_agency_match_pct": float(
                100.0 * rows["implementing_agency_match"].mean()
            ),
        }
    return audit


def duplicate_audit_payload(
    candidates: pd.DataFrame,
    summary: pd.DataFrame,
    embedding_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the reproducible Day-4.1 duplicate selectivity audit payload."""

    scores = candidates["duplicate_similarity_score_0_100"]
    percentiles = {
        "count": int(scores.notna().sum()),
        "minimum": float(scores.min()),
        "p50": _series_percentile(scores, 0.50),
        "p75": _series_percentile(scores, 0.75),
        "p90": _series_percentile(scores, 0.90),
        "p95": _series_percentile(scores, 0.95),
        "p97_5": _series_percentile(scores, 0.975),
        "p99": _series_percentile(scores, 0.99),
        "maximum": float(scores.max()),
    }
    thresholds = {
        f"at_or_above_{threshold:g}": int(scores.ge(threshold).sum())
        for threshold in (80.0, 85.0, 90.0, 92.5, 95.0)
    }
    return {
        "embedding_model": embedding_metadata["embedding_model"],
        "embedding_count": int(embedding_metadata["embedding_count"]),
        "unique_candidate_pairs_evaluated": int(len(candidates)),
        "retrieval_candidate_pair_count": int(candidates["retrieval_candidate"].sum()),
        "historical_candidate_threshold_0_100": DUPLICATE_CANDIDATE_THRESHOLD,
        "historical_candidate_pair_count": int(candidates["candidate_flag"].sum()),
        "works_with_historical_candidate": int(
            summary["duplicate_candidate_count"].gt(0).sum()
        ),
        "review_candidate_pair_count": int(candidates["review_candidate"].sum()),
        "works_with_review_candidate": int(summary["review_candidate"].sum()),
        "review_policy": {
            "minimum_composite_score_0_100": REVIEW_MIN_SCORE,
            "minimum_text_cosine_similarity": REVIEW_MIN_TEXT_SIMILARITY,
            "required_local_matches": ["district", "block", "village"],
            "maximum_geographic_distance_km": REVIEW_MAX_DISTANCE_KM,
            "minimum_amount_similarity": REVIEW_MIN_AMOUNT_SIMILARITY,
            "maximum_recommendation_date_difference_days": (
                REVIEW_MAX_DATE_DIFFERENCE_DAYS
            ),
            "required_taxonomy_matches": ["sector", "sub_sector"],
            "implementing_agency_match_required": False,
            "interpretation": (
                "Conservative evidence-based review selection; it does not "
                "establish work identity or wrongdoing."
            ),
        },
        "score_distribution": percentiles,
        "score_threshold_counts": thresholds,
        "structured_evidence_audit": _structured_evidence_audit(candidates),
    }


def _refresh_existing_day4_summary(
    processed: Path, duplicate_payload: Mapping[str, Any]
) -> None:
    summary_path = processed / "day4_detector_summary.json"
    if not summary_path.is_file():
        return
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["duplicates"] = dict(duplicate_payload)
    _write_json(summary_path, payload)


def generate_or_load_embeddings(
    works: pd.DataFrame,
    paths: ProjectPaths,
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> tuple[np.ndarray, Path, Path, dict[str, Any]]:
    """Persist/reuse one normalized local embedding per governed work row."""

    if not works["work_id"].is_unique:
        raise ValueError("Duplicate embedding input requires unique work IDs")
    work_ids = works["work_id"].astype(str).tolist()
    texts = build_duplicate_search_text(works).tolist()
    input_hash = _text_contract_hash(work_ids, texts)
    processed = paths.ensure_processed_data_dir()
    embedding_path = processed / "duplicate_work_embeddings.npy"
    metadata_path = processed / "duplicate_work_embeddings_metadata.json"

    if embedding_path.is_file() and metadata_path.is_file():
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        embeddings = np.load(embedding_path, allow_pickle=False)
        if (
            existing.get("embedding_model") == model_name
            and existing.get("normalized_text_contract_sha256") == input_hash
            and existing.get("work_ids") == work_ids
            and embeddings.shape[0] == len(work_ids)
        ):
            return embeddings, embedding_path, metadata_path, existing

    model_cache = paths.models_dir / "duplicates" / "sentence_transformers_cache"
    model_cache.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(
        model_name,
        cache_folder=str(model_cache),
        device="cpu",
    )
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32", copy=False)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(work_ids):
        raise RuntimeError("Embedding model did not return one vector per work")
    norms = np.linalg.norm(embeddings, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-5):
        raise RuntimeError("Cosine embeddings were not normalized")
    np.save(embedding_path, embeddings, allow_pickle=False)
    metadata = {
        "artifact_type": "local duplicate-work semantic embeddings",
        "embedding_model": model_name,
        "sentence_transformers_version": sentence_transformers.__version__,
        "embedding_count": int(embeddings.shape[0]),
        "embedding_dimension": int(embeddings.shape[1]),
        "embedding_dtype": str(embeddings.dtype),
        "normalized_embeddings": True,
        "device": "cpu",
        "normalized_text_contract_sha256": input_hash,
        "text_fields": [
            "work_description",
            "sector",
            "sub_sector",
            "state_name",
            "district",
            "block",
            "village",
        ],
        "text_normalization": "NFKC, lowercase/casefold, light punctuation cleanup, whitespace normalization",
        "external_project_text_api_used": False,
        "evaluation_labels_used": False,
        "work_ids": work_ids,
    }
    _write_json(metadata_path, metadata)
    return embeddings, embedding_path, metadata_path, metadata


def run_duplicate_detector(
    paths: ProjectPaths | None = None,
) -> DuplicateArtifacts:
    """Run production duplicate candidate generation without evaluation helpers."""

    resolved = paths or ProjectPaths.discover()
    bundle = load_operational_data(resolved)
    embeddings, embedding_path, metadata_path, metadata = generate_or_load_embeddings(
        bundle.works, resolved
    )
    work_ids = metadata["work_ids"]
    retrieved = retrieve_cosine_candidate_pairs(
        embeddings,
        work_ids,
        top_neighbors=TOP_NEIGHBORS_PER_WORK,
    )
    candidates, summary = build_duplicate_candidates(bundle.works, retrieved)
    candidate_path = resolved.processed_data_dir / "duplicate_candidates.csv"
    summary_path = resolved.processed_data_dir / "duplicate_summary.csv"
    candidates.to_csv(candidate_path, index=False, encoding="utf-8")
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    audit_payload = duplicate_audit_payload(candidates, summary, metadata)
    metadata.update(
        {
            "nearest_neighbors_per_work": TOP_NEIGHBORS_PER_WORK,
            "unique_candidate_pairs_evaluated": int(len(candidates)),
            "prototype_candidate_threshold_0_100": DUPLICATE_CANDIDATE_THRESHOLD,
            "candidate_pair_count": int(candidates["candidate_flag"].sum()),
            "retrieval_candidate_pair_count": int(
                candidates["retrieval_candidate"].sum()
            ),
            "review_candidate_pair_count": int(candidates["review_candidate"].sum()),
            "works_with_review_candidate": int(summary["review_candidate"].sum()),
            "review_policy": audit_payload["review_policy"],
            "score_distribution_audit": audit_payload["score_distribution"],
            "score_threshold_counts": audit_payload["score_threshold_counts"],
            "structured_evidence_audit": audit_payload[
                "structured_evidence_audit"
            ],
            "score_weights": dict(DUPLICATE_SCORE_WEIGHTS),
            "score_formula": (
                "100 * weighted available mean of: 0.50 text cosine + 0.15 location "
                "+ 0.15 amount + 0.10 date proximity + 0.05 sector match + "
                "0.03 sub-sector match + 0.02 implementing-agency match"
            ),
            "threshold_interpretation": (
                "The historical score>=75 field is retained for compatibility; "
                "review_candidate is the conservative operational review queue. "
                "Neither field is an MPLADS rule, legal conclusion, identity "
                "determination, or finding of wrongdoing."
            ),
        }
    )
    _write_json(metadata_path, metadata)
    _refresh_existing_day4_summary(resolved.processed_data_dir, audit_payload)
    return DuplicateArtifacts(
        embeddings=embedding_path,
        embedding_metadata=metadata_path,
        candidates=candidate_path,
        summary=summary_path,
    )


def main() -> int:
    artifacts = run_duplicate_detector()
    print(f"Embeddings: {artifacts.embeddings}")
    print(f"Embedding metadata: {artifacts.embedding_metadata}")
    print(f"Duplicate candidates: {artifacts.candidates}")
    print(f"Duplicate summary: {artifacts.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
