from __future__ import annotations

import os
from typing import Annotated

import chromadb
from chromadb.utils import embedding_functions
import dotenv

from agent_framework import ai_function
from pydantic import Field

from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

_EMBED_MODEL = "text-embedding-3-small"
_EMBEDDING_FN = embedding_functions.OpenAIEmbeddingFunction(
    model_name=_EMBED_MODEL,
    deployment_id=_EMBED_MODEL,
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_type="azure",
    api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
)

_MAX_CHUNK_CHARS = 900
_MAX_CHUNK_OVERLAP = 90


def load_pdf_chunks() -> list[Document]:
    loader = PyPDFLoader(
        file_path=Path(__file__).resolve().parent.parent
        / "data"
        / "GuideToTotalJointSurgery_ENG_V2.pdf",
        extract_images=False,
    )

    pages = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=_MAX_CHUNK_CHARS,
        chunk_overlap=_MAX_CHUNK_OVERLAP,
    )

    return text_splitter.split_documents(pages)


dotenv.load_dotenv()


class MedicalGuidanceSearch:
    """Encapsulates the logic for searching medical guidance."""

    _DEFAULT_TOP_K = 4

    def __init__(
        self,
        persistent_path: str | None = None,
    ) -> None:
        self._persistent_path = persistent_path
        self._collection = self._get_or_build_collection()

    def _get_or_build_collection(self) -> chromadb.Collection | None:
        """Initializes the ChromaDB collection, building it if necessary."""
        try:
            chunks = load_pdf_chunks()
        except FileNotFoundError:
            print("Warning: Guidance PDF not found when building the search index.")
            return None
        except Exception as exc:  # pragma: no cover - defensive logging only
            print(f"Warning: Failed to load guidance PDF: {exc}")
            return None

        if not chunks:
            print("Warning: No document chunks were generated from the guide.")
            return None

        docs = [chunk.page_content for chunk in chunks]
        metadatas = [
            {
                "source": "Your Guide to Total Joint Replacement",
                "page": chunk.metadata.get("page", 0),
                "page_label": chunk.metadata.get("page_label", ""),
            }
            for chunk in chunks
        ]

        return self._build_chroma_collection(docs, metadatas)

    def _build_chroma_collection(
        self, docs: list[str], metadatas: list[dict] | None = None
    ) -> chromadb.Collection:
        """Builds and returns a ChromaDB collection from documents."""
        if self._persistent_path:
            chroma_client = chromadb.PersistentClient(path=self._persistent_path)
        else:
            chroma_client = chromadb.EphemeralClient()

        coll = chroma_client.get_or_create_collection(
            name="medical_guidance",
            embedding_function=_EMBEDDING_FN,
        )

        if coll.count() == 0:
            ids = [f"doc_{i}" for i in range(len(docs))]
            coll.add(documents=docs, metadatas=metadatas, ids=ids)
        return coll

    def search(
        self, query: str, k: int | None = None
    ) -> list[dict[str, str | float | None]]:
        """Performs a search query against the ChromaDB collection."""
        if self._collection is None:
            return []

        k = k if k is not None else self._DEFAULT_TOP_K
        res = self._collection.query(query_texts=[query], n_results=max(k, 1))

        documents = res.get("documents", [[]])[0]
        if not documents:
            return []

        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        return [
            {
                "text": documents[i],
                "metadata": metadatas[i] if metadatas and i < len(metadatas) else None,
                "distance": float(distances[i])
                if distances and i < len(distances)
                else -1.0,
            }
            for i in range(len(documents))
        ]


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
) -> dict[str, list[dict[str, str | float | int]] | str]:
    """
    Asynchronously searches medical guidance.

    This function is a wrapper around the GuidanceSearch class instance.
    """
    print(f"Searching medical guidance for query: '{query}' with top_k={top_k}")
    if not query.strip():
        return {
            "matches": [],
            "message": "The search query was empty. Please provide a question or keywords.",
        }

    if _search_instance is None:
        return {
            "matches": [],
            "message": "The medical guidance search service is not available.",
        }

    matches = _search_instance.search(query, k=top_k)
    if not matches:
        print(f"No matches found for query: '{query}'")
        return {
            "matches": [],
            "message": "No relevant sections were found in the local guide.",
        }

    print(f"Search found {len(matches)} matches for query: '{query}'")
    return {"matches": matches}


if __name__ == "__main__":
    import asyncio

    async def main():
        query = "What are the risks of total joint replacement surgery?"
        result = await search_medical_guidance(query=query, top_k=3)
        for i, match in enumerate(result["matches"]):
            print(f"--- Match {i + 1} ---")
            print(f"Text: {match['text']}")
            print(f"Metadata: {match['metadata']}")
            print(f"Distance: {match['distance']}")
            print()

    asyncio.run(main())
