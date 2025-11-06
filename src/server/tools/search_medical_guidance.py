from __future__ import annotations

import logging
import os
from typing import Annotated, Any

import dotenv
import chromadb
from chromadb.utils import embedding_functions

from agent_framework import ai_function
from pydantic import BaseModel, Field

from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

_EMBED_MODEL = "text-embedding-3-small"
_DEFAULT_GUIDE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "GuideToTotalJointSurgery_ENG_V2.pdf"
)
_METADATA_SOURCE = "Your Guide to Total Joint Replacement"


def _load_embedding_function() -> embedding_functions.OpenAIEmbeddingFunction | None:
    required_vars = ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        logger.warning(
            "Medical guidance search disabled; missing environment variables: %s",
            ", ".join(sorted(missing)),
        )
        return None

    try:
        return embedding_functions.OpenAIEmbeddingFunction(
            model_name=_EMBED_MODEL,
            deployment_id=_EMBED_MODEL,
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_type="azure",
            api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning(
            "Medical guidance search disabled; failed to initialise embedding function: %s",
            exc,
        )
        return None


_EMBEDDING_FN = _load_embedding_function()

_MAX_CHUNK_CHARS = 900
_MAX_CHUNK_OVERLAP = 90


class GuidanceMatch(BaseModel):
    text: str
    metadata: dict[str, Any] | None = None
    distance: float


class GuidanceSearchResult(BaseModel):
    matches: list[GuidanceMatch] = Field(default_factory=list)
    message: str | None = None


def load_pdf_chunks(
    guide_path: Path,
    *,
    chunk_size: int = _MAX_CHUNK_CHARS,
    chunk_overlap: int = _MAX_CHUNK_OVERLAP,
) -> list[Document]:
    loader = PyPDFLoader(file_path=str(guide_path), extract_images=False)

    pages = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return text_splitter.split_documents(pages)


class MedicalGuidanceSearch:
    """Encapsulates the logic for searching medical guidance."""

    _DEFAULT_TOP_K = 4

    def __init__(
        self,
        persistent_path: str | None = None,
        guide_path: Path | str | None = None,
        embedding_fn: embedding_functions.OpenAIEmbeddingFunction | None = None,
    ) -> None:
        self._persistent_path = persistent_path
        self._guide_path = Path(guide_path) if guide_path else _DEFAULT_GUIDE_PATH
        self._embedding_fn = embedding_fn or _EMBEDDING_FN
        self._collection: chromadb.Collection | None = None

        if self._embedding_fn is None:
            logger.warning(
                "Medical guidance search unavailable; embedding function is not configured.",
            )
            return

        self._collection = self._get_or_build_collection()

    def _get_or_build_collection(self) -> chromadb.Collection | None:
        """Initializes the ChromaDB collection, building it if necessary."""
        client = self._create_client()

        collection = client.get_or_create_collection(
            name="medical_guidance",
            embedding_function=self._embedding_fn,
        )

        if collection.count() > 0:
            return collection

        chunks = self._load_chunks()
        if not chunks:
            return None

        docs, metadatas = self._prepare_documents(chunks)
        if not docs:
            logger.warning("Medical guidance search disabled; no documents to index.")
            return None

        try:
            self._ingest_documents(collection, docs, metadatas)
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.warning("Failed to ingest guidance documents: %s", exc)
            return None

        return collection

    def _create_client(self):
        if self._persistent_path:
            return chromadb.PersistentClient(path=self._persistent_path)
        return chromadb.EphemeralClient()

    def _load_chunks(self) -> list[Document]:
        try:
            return load_pdf_chunks(self._guide_path)
        except FileNotFoundError:
            logger.warning(
                "Medical guidance PDF not found at %s; search will be unavailable.",
                self._guide_path,
            )
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.warning("Failed to load guidance PDF: %s", exc)
        return []

    def _prepare_documents(
        self, chunks: list[Document]
    ) -> tuple[list[str], list[dict[str, Any]]]:
        docs: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            text = chunk.page_content.strip()
            if not text:
                continue

            docs.append(text)
            metadatas.append(
                {
                    "source": chunk.metadata.get("source", _METADATA_SOURCE),
                    "page": chunk.metadata.get("page", 0),
                    "page_label": chunk.metadata.get("page_label", ""),
                }
            )
        return docs, metadatas

    def _ingest_documents(
        self,
        collection: chromadb.Collection,
        docs: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        ids = [f"doc_{i}" for i in range(len(docs))]
        collection.add(documents=docs, metadatas=metadatas, ids=ids)

    @property
    def is_available(self) -> bool:
        return self._collection is not None

    def search(self, query: str, k: int | None = None) -> list[GuidanceMatch]:
        """Performs a search query against the ChromaDB collection."""
        if self._collection is None:
            logger.info("Medical guidance search requested but no index is loaded.")
            return []

        k = k if k is not None else self._DEFAULT_TOP_K
        res = self._collection.query(query_texts=[query], n_results=max(k, 1))

        documents = res.get("documents", [[]])[0]
        if not documents:
            return []

        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        matches: list[GuidanceMatch] = []
        for idx, text in enumerate(documents):
            metadata = metadatas[idx] if metadatas and idx < len(metadatas) else None
            distance = (
                float(distances[idx])
                if distances and idx < len(distances)
                else -1.0
            )
            matches.append(
                GuidanceMatch(
                    text=text,
                    metadata=metadata,
                    distance=distance,
                )
            )

        return matches


# --- Global Instance ---

_search_instance = MedicalGuidanceSearch()


@ai_function(
    name="search_medical_guidance",
    description="Searches the available medical guidance and returns the most relevant excerpts.",
)
async def search_medical_guidance(
    query: Annotated[
        str,
        Field(
            description="The natural language question or topic to look up in the guidance."
        ),
    ],
    top_k: Annotated[
        int, Field(description="Number of excerpts to return.")
    ] = MedicalGuidanceSearch._DEFAULT_TOP_K,
) -> dict[str, Any]:
    """
    Asynchronously searches medical guidance.

    This function is a wrapper around the GuidanceSearch class instance.
    """
    logger.info(
        "Searching medical guidance for query='%s' with top_k=%s", query, top_k
    )

    if not query.strip():
        return GuidanceSearchResult(
            matches=[],
            message="The search query was empty. Please provide a question or keywords.",
        ).model_dump()

    if _search_instance is None or not _search_instance.is_available:
        return GuidanceSearchResult(
            matches=[],
            message="The medical guidance search service is not available.",
        ).model_dump()

    matches = _search_instance.search(query, k=top_k)
    if not matches:
        logger.info("No matches found for query='%s'", query)
        return GuidanceSearchResult(
            matches=[],
            message="No relevant sections were found in the local guide.",
        ).model_dump()

    logger.info("Search found %s matches for query='%s'", len(matches), query)
    return GuidanceSearchResult(matches=matches).model_dump()


if __name__ == "__main__":
    import asyncio

    async def main():
        query = "What are the risks of total joint replacement surgery?"
        result = await search_medical_guidance(query=query, top_k=3)
        if result.get("message"):
            print(result["message"])
        for i, match in enumerate(result["matches"]):
            print(f"--- Match {i + 1} ---")
            print(f"Text: {match['text']}")
            print(f"Metadata: {match['metadata']}")
            print(f"Distance: {match['distance']}")
            print()

    asyncio.run(main())
