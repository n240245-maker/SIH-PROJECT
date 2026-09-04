"""Two-channel direct-clause plus local semantic guideline retrieval."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from intelligence.data.paths import ProjectPaths

from .embeddings import EMBEDDING_MODEL, generate_or_load_guideline_embeddings
from .models import RetrievedGuidelineChunk


DIRECT_RULE_REFERENCE = "DIRECT_RULE_REFERENCE"
SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
DEFAULT_TOP_K = 5
DEFAULT_CONTEXT_CAP = 10


class GuidelineRetriever:
    """Small in-memory cosine index over verified local guideline chunks."""

    def __init__(
        self,
        paths: ProjectPaths,
        *,
        top_k: int = DEFAULT_TOP_K,
        context_cap: int = DEFAULT_CONTEXT_CAP,
    ) -> None:
        if top_k < 1 or context_cap < 1:
            raise ValueError("top_k and context_cap must be positive")
        self.paths = paths
        self.top_k = top_k
        self.context_cap = context_cap
        self.embeddings, self.chunks, self.metadata = (
            generate_or_load_guideline_embeddings(paths)
        )
        self._by_id = {str(chunk["chunk_id"]): chunk for chunk in self.chunks}
        self._model = None

    def _encode_query(self, query: str) -> np.ndarray:
        if self._model is None:
            from .embeddings import load_local_embedding_model

            self._model = load_local_embedding_model(self.paths, EMBEDDING_MODEL)
        vector = self._model.encode(
            [query],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0].astype("float32", copy=False)
        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5):
            raise RuntimeError("Query embedding is not normalized")
        return vector

    def _result(
        self,
        chunk: dict[str, Any],
        method: str,
        similarity: float | None,
    ) -> RetrievedGuidelineChunk:
        return RetrievedGuidelineChunk(
            chunk_id=str(chunk["chunk_id"]),
            page_start=int(chunk["page_start"]),
            page_end=int(chunk["page_end"]),
            chapter=str(chunk["chapter"]),
            clause_identifiers=chunk.get("section_or_clause"),
            retrieval_method=method,
            cosine_similarity=similarity,
            guideline_version=str(chunk["guideline_version"]),
            guideline_sha256=str(chunk["source_file_sha256"]).upper(),
            text=str(chunk["text"]),
        )

    def retrieve(
        self,
        query: str,
        *,
        direct_chunk_ids: Iterable[str] = (),
    ) -> list[RetrievedGuidelineChunk]:
        if not query.strip():
            raise ValueError("Retrieval query cannot be empty")
        unique_direct = list(dict.fromkeys(str(item) for item in direct_chunk_ids))
        missing = [item for item in unique_direct if item not in self._by_id]
        if missing:
            raise KeyError(f"Direct guideline chunks do not exist: {missing}")

        vector = self._encode_query(query)
        return self._retrieve_vector(vector, unique_direct)

    def _retrieve_vector(
        self, vector: np.ndarray, direct_chunk_ids: Iterable[str]
    ) -> list[RetrievedGuidelineChunk]:
        unique_direct = list(dict.fromkeys(str(item) for item in direct_chunk_ids))
        missing = [item for item in unique_direct if item not in self._by_id]
        if missing:
            raise KeyError(f"Direct guideline chunks do not exist: {missing}")
        similarities = self.embeddings @ vector
        order = np.argsort(-similarities, kind="stable")
        results = [
            self._result(self._by_id[chunk_id], DIRECT_RULE_REFERENCE, None)
            for chunk_id in unique_direct
        ]
        retained = set(unique_direct)
        semantic_count = 0
        effective_cap = max(self.context_cap, len(results))
        for index in order:
            chunk_id = str(self.chunks[int(index)]["chunk_id"])
            if chunk_id in retained:
                continue
            if semantic_count >= self.top_k or len(results) >= effective_cap:
                break
            results.append(
                self._result(
                    self.chunks[int(index)],
                    SEMANTIC_SIMILARITY,
                    float(similarities[int(index)]),
                )
            )
            retained.add(chunk_id)
            semantic_count += 1
        return results

    def retrieve_many(
        self,
        queries: list[str],
        direct_chunk_ids: list[Iterable[str]],
    ) -> list[list[RetrievedGuidelineChunk]]:
        """Batch local query encoding for the 3,000-record context artifact."""

        if len(queries) != len(direct_chunk_ids):
            raise ValueError("Queries and direct-reference lists must align")
        if any(not query.strip() for query in queries):
            raise ValueError("Retrieval queries cannot be empty")
        if self._model is None:
            from .embeddings import load_local_embedding_model

            self._model = load_local_embedding_model(self.paths, EMBEDDING_MODEL)
        vectors = self._model.encode(
            queries,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32", copy=False)
        return [
            self._retrieve_vector(vector, direct)
            for vector, direct in zip(vectors, direct_chunk_ids, strict=True)
        ]
