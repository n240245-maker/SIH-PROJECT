"""Local, reproducible embeddings for the verified guideline corpus."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from intelligence.data.paths import ProjectPaths


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_CHUNK_COUNT = 61
NORMALIZATION = "L2_UNIT_NORM"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_verified_guideline_contract(
    paths: ProjectPaths,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Load chunks and fail closed if their identity differs from the manifest."""

    chunks = _read_json(paths.processed_data_dir / "guideline_chunks.json")
    manifest = _read_json(paths.processed_data_dir / "guideline_manifest.json")
    if not isinstance(chunks, list) or len(chunks) != EXPECTED_CHUNK_COUNT:
        count = len(chunks) if isinstance(chunks, list) else "non-list"
        raise ValueError(f"Expected {EXPECTED_CHUNK_COUNT} guideline chunks, found {count}")
    ordered_ids = [str(chunk.get("chunk_id")) for chunk in chunks]
    if len(set(ordered_ids)) != EXPECTED_CHUNK_COUNT:
        raise ValueError("Guideline chunk IDs must be unique")
    guideline_hash = str(manifest.get("sha256", "")).upper()
    if not guideline_hash:
        raise ValueError("Guideline manifest has no SHA-256")
    mismatches = [
        chunk["chunk_id"]
        for chunk in chunks
        if str(chunk.get("source_file_sha256", "")).upper() != guideline_hash
    ]
    if mismatches:
        raise ValueError(f"Guideline chunks do not match manifest SHA-256: {mismatches}")
    contract = [
        {
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "source_file_sha256": chunk["source_file_sha256"],
        }
        for chunk in chunks
    ]
    serialized = json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return chunks, manifest, hashlib.sha256(serialized).hexdigest().upper()


def _metadata_valid(
    metadata: dict[str, Any],
    embeddings: np.ndarray,
    chunks: list[dict[str, Any]],
    manifest: dict[str, Any],
    contract_hash: str,
    model_name: str,
) -> bool:
    return bool(
        metadata.get("embedding_model") == model_name
        and metadata.get("chunk_count") == len(chunks)
        and metadata.get("ordered_chunk_ids")
        == [chunk["chunk_id"] for chunk in chunks]
        and str(metadata.get("guideline_sha256", "")).upper()
        == str(manifest["sha256"]).upper()
        and metadata.get("chunk_text_contract_sha256") == contract_hash
        and metadata.get("normalization") == NORMALIZATION
        and embeddings.ndim == 2
        and embeddings.shape[0] == len(chunks)
        and metadata.get("embedding_dimension") == embeddings.shape[1]
        and np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5)
    )


def load_local_embedding_model(
    paths: ProjectPaths, model_name: str = EMBEDDING_MODEL
) -> SentenceTransformer:
    """Load the project-cached encoder; no external embedding API is used."""

    cache = paths.models_dir / "duplicates" / "sentence_transformers_cache"
    cache.mkdir(parents=True, exist_ok=True)
    return SentenceTransformer(
        model_name,
        cache_folder=str(cache),
        device="cpu",
        local_files_only=True,
    )


def generate_or_load_guideline_embeddings(
    paths: ProjectPaths,
    *,
    model_name: str = EMBEDDING_MODEL,
    force: bool = False,
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    """Return a normalized vector per ordered chunk, reusing a valid artifact."""

    chunks, manifest, contract_hash = load_verified_guideline_contract(paths)
    destination = paths.ensure_processed_data_dir()
    embedding_path = destination / "guideline_embeddings.npy"
    metadata_path = destination / "guideline_embedding_metadata.json"
    if not force and embedding_path.is_file() and metadata_path.is_file():
        embeddings = np.load(embedding_path, allow_pickle=False)
        metadata = _read_json(metadata_path)
        if _metadata_valid(
            metadata, embeddings, chunks, manifest, contract_hash, model_name
        ):
            return embeddings, chunks, metadata

    model = load_local_embedding_model(paths, model_name)
    embeddings = model.encode(
        [str(chunk["text"]) for chunk in chunks],
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32", copy=False)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
        raise RuntimeError("Embedding encoder did not return one row per chunk")
    if not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5):
        raise RuntimeError("Guideline embeddings are not L2 normalized")
    np.save(embedding_path, embeddings, allow_pickle=False)
    metadata = {
        "embedding_model": model_name,
        "embedding_dimension": int(embeddings.shape[1]),
        "chunk_count": len(chunks),
        "ordered_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
        "guideline_sha256": str(manifest["sha256"]).upper(),
        "chunk_text_contract_sha256": contract_hash,
        "normalization": NORMALIZATION,
        "library_version": version("sentence-transformers"),
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return embeddings, chunks, metadata
