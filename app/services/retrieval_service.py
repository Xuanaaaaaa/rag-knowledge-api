from __future__ import annotations

from typing import Any

from FlagEmbedding import FlagReranker

from app.config import Settings
from app.core.embedder import get_embeddings
from app.core.vectorstore import VectorStore
from app.services.llm_service import LLMService

_REWRITE_SYSTEM = (
    "你是一个查询优化助手。将用户的问题改写为更适合向量检索的表达："
    "去除口语化、补全隐含主语、拆解复合问题。只输出改写后的问题，不要解释。"
)

_reranker_instance: FlagReranker | None = None


def _get_reranker() -> FlagReranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = FlagReranker("BAAI/bge-reranker-base", use_fp16=True)
    return _reranker_instance


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        vectorstore: VectorStore,
        llm_service: LLMService,
    ) -> None:
        self._settings = settings
        self._vectorstore = vectorstore
        self._llm_service = llm_service

    async def rewrite_query(self, question: str) -> str:
        rewritten = await self._llm_service.generate(
            prompt=question, system=_REWRITE_SYSTEM
        )
        return rewritten.strip() or question

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        reranker = _get_reranker()
        pairs = [[query, c["document"]] for c in candidates]
        scores = reranker.compute_score(pairs, normalize=True)
        if isinstance(scores[0], list):
            scores = scores[0]
        ranked = sorted(
            zip(scores, candidates), key=lambda x: x[0], reverse=True
        )
        results = []
        for score, candidate in ranked[:top_k]:
            results.append({**candidate, "rerank_score": float(score)})
        return results

    async def retrieve(
        self,
        question: str,
        collection_name: str = "default",
    ) -> tuple[str, list[dict[str, Any]]]:
        rewritten = await self.rewrite_query(question)

        embeddings = await get_embeddings(
            [rewritten],
            model=self._settings.ollama_embed_model,
            base_url=self._settings.ollama_base_url,
        )
        query_embedding = embeddings[0]

        candidates = await self._vectorstore.query(
            collection_name=collection_name,
            query_embedding=query_embedding,
            n_results=self._settings.top_k_retrieve,
        )

        reranked = self.rerank(rewritten, candidates, top_k=self._settings.top_k_rerank)
        return rewritten, reranked
