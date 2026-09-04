"""Day-8 local embedding and two-channel retrieval contracts."""

from __future__ import annotations

import json

import numpy as np

from rag.embeddings import EMBEDDING_MODEL, load_verified_guideline_contract
from rag.retrieval import DIRECT_RULE_REFERENCE, SEMANTIC_SIMILARITY, GuidelineRetriever


def test_guideline_embedding_contract_is_exact(project_paths):
    processed = project_paths.processed_data_dir
    metadata = json.loads(
        (processed / "guideline_embedding_metadata.json").read_text(encoding="utf-8")
    )
    embeddings = np.load(processed / "guideline_embeddings.npy", allow_pickle=False)
    chunks, manifest, contract_hash = load_verified_guideline_contract(project_paths)
    assert len(chunks) == metadata["chunk_count"] == embeddings.shape[0] == 61
    assert embeddings.shape[1] == metadata["embedding_dimension"] == 384
    assert metadata["embedding_model"] == EMBEDDING_MODEL
    assert metadata["ordered_chunk_ids"] == [row["chunk_id"] for row in chunks]
    assert metadata["guideline_sha256"] == manifest["sha256"]
    assert metadata["chunk_text_contract_sha256"] == contract_hash
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5)


def test_retrieval_is_deterministic_bounded_and_local(day8_retriever):
    query = "completion utilization certificate asset handover"
    first = day8_retriever.retrieve(query)
    second = day8_retriever.retrieve(query)
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert len(first) == 5
    assert all(item.retrieval_method == SEMANTIC_SIMILARITY for item in first)
    assert all(item.cosine_similarity is not None for item in first)
    known = {row["chunk_id"] for row in day8_retriever.chunks}
    assert {item.chunk_id for item in first}.issubset(known)


def test_direct_rule_chunks_cannot_be_displaced(project_paths):
    retriever = GuidelineRetriever(project_paths, top_k=1, context_cap=1)
    direct = ["MPLADS-2023-P019", "MPLADS-2023-P051"]
    results = retriever.retrieve("unrelated statistical trend", direct_chunk_ids=direct)
    assert [item.chunk_id for item in results[:2]] == direct
    assert all(item.retrieval_method == DIRECT_RULE_REFERENCE for item in results[:2])
    assert sum(item.retrieval_method == SEMANTIC_SIMILARITY for item in results) <= 1


def test_embedding_implementation_has_no_external_embedding_service(project_paths):
    source = (project_paths.project_root / "code/rag/embeddings.py").read_text(
        encoding="utf-8"
    )
    assert "local_files_only=True" in source
    assert "openai" not in source.casefold()
    assert "httpx" not in source.casefold()
    assert "requests." not in source.casefold()
