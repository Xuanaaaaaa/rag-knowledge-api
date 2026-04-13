from __future__ import annotations

import asyncio
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    def __init__(self, persist_dir: str) -> None:
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(name=name)

    async def add_chunks(
        self,
        collection_name: str,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

        def _add() -> None:
            col = self._get_or_create_collection(collection_name)
            col.add(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        await asyncio.to_thread(_add)

    async def delete_by_doc_id(self, collection_name: str, doc_id: str) -> None:
        def _delete() -> None:
            col = self._get_or_create_collection(collection_name)
            results = col.get(where={"doc_id": doc_id})
            if results["ids"]:
                col.delete(ids=results["ids"])

        await asyncio.to_thread(_delete)

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        n_results: int,
    ) -> list[dict[str, Any]]:
        def _query() -> list[dict[str, Any]]:
            col = self._get_or_create_collection(collection_name)
            results = col.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            items = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append({"document": doc, "metadata": meta, "distance": dist})
            return items

        return await asyncio.to_thread(_query)

    async def list_documents(self, collection_name: str) -> list[dict[str, Any]]:
        def _list() -> list[dict[str, Any]]:
            col = self._get_or_create_collection(collection_name)
            results = col.get(include=["metadatas"])
            seen: dict[str, dict[str, Any]] = {}
            for meta in results["metadatas"]:
                doc_id = meta.get("doc_id", "")
                if doc_id not in seen:
                    seen[doc_id] = meta
            return list(seen.values())

        return await asyncio.to_thread(_list)
