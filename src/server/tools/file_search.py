from __future__ import annotations

from collections import Counter
import math
import re
from pathlib import Path
from typing import Annotated

from agent_framework import AIFunction, ai_function
from pydantic import Field

_TOKEN_PATTERN = re.compile(r"\b\w+\b")
_DEFAULT_TOP_K = 5


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def _chunk_text(text: str, *, chunk_size: int = 160, overlap: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        if end == len(words):
            break
    return chunks


class _LocalVectorStore:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self._doc_vectors: list[tuple[dict[str, float], float]] = []
        self._idf: dict[str, float] = {}
        self._build_index()

    def _build_index(self) -> None:
        doc_term_counts: list[Counter[str]] = []
        doc_freq: Counter[str] = Counter()

        for chunk in self._chunks:
            tokens = _tokenize(chunk)
            counts = Counter(tokens)
            doc_term_counts.append(counts)
            doc_freq.update(counts.keys())

        doc_count = max(len(self._chunks), 1)
        self._idf = {
            term: math.log((1 + doc_count) / (1 + freq)) + 1
            for term, freq in doc_freq.items()
        }

        self._doc_vectors = []
        for counts in doc_term_counts:
            vector = {
                term: count * self._idf.get(term, 0.0) for term, count in counts.items()
            }
            norm = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
            self._doc_vectors.append((vector, norm))

    def search(self, query: str, *, top_k: int) -> list[dict[str, str | float | int]]:
        query_tokens = Counter(_tokenize(query))
        query_vector = {
            term: count * self._idf.get(term, 0.0)
            for term, count in query_tokens.items()
            if term in self._idf
        }
        if not query_vector:
            return []

        query_norm = (
            math.sqrt(sum(weight * weight for weight in query_vector.values())) or 1.0
        )

        scored_results: list[tuple[float, int]] = []
        for idx, (doc_vector, doc_norm) in enumerate(self._doc_vectors):
            dot_product = sum(
                query_vector.get(term, 0.0) * weight
                for term, weight in doc_vector.items()
            )
            if dot_product <= 0:
                continue
            score = dot_product / (query_norm * doc_norm)
            if score > 0:
                scored_results.append((score, idx))

        scored_results.sort(reverse=True)
        matches = []
        for score, idx in scored_results[: max(top_k, 1)]:
            matches.append(
                {
                    "excerpt": self._chunks[idx],
                    "score": round(score, 4),
                    "chunk_index": idx,
                }
            )
        return matches


def _load_local_vector_store() -> _LocalVectorStore | None:
    guide_path = (
        Path(__file__).parent.parent / "knowledge" / "joint_replacement_guide_layout.md"
    )
    try:
        guide_text = guide_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"WARNING: Guide not found at {guide_path}. File search tool disabled.")
        return None

    chunks = _chunk_text(guide_text)
    if not chunks:
        print("WARNING: Guide content is empty. File search tool disabled.")
        return None

    return _LocalVectorStore(chunks)


_VECTOR_STORE = _load_local_vector_store()


@ai_function(
    name="joint_surgery_guide_search",
    description="Searches the local joint surgery guide and returns the most relevant excerpts.",
)
async def _search_joint_surgery_guide(
    query: Annotated[
        str,
        Field(
            description="The natural language question or topic to look up in the guide."
        ),
    ],
    top_k: Annotated[
        int, Field(description="Number of excerpts to return.")
    ] = _DEFAULT_TOP_K,
) -> dict[str, list[dict[str, str | float | int]] | str]:
    if not query.strip():
        return {
            "matches": [],
            "message": "The search query was empty. Please provide a question or keywords.",
        }

    if _VECTOR_STORE is None:
        return {
            "matches": [],
            "message": "Joint surgery guide is not available on this server.",
        }

    matches = _VECTOR_STORE.search(query, top_k=max(top_k, 1))
    if not matches:
        return {
            "matches": [],
            "message": "No relevant sections were found in the local guide.",
        }

    return {"matches": matches}


def file_search_tool() -> AIFunction:
    """Returns a local RAG-backed search tool for the joint surgery guide."""

    return _search_joint_surgery_guide
