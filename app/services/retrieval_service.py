from __future__ import annotations

from typing import Any

from FlagEmbedding import FlagReranker

from app.config import Settings
from app.core.embedder import get_embeddings
from app.core.vectorstore import VectorStore
from app.services.llm_service import LLMService

_REWRITE_SYSTEM = (
    "你是一个查询优化助手。结合对话历史，将用户的最新问题改写为独立、完整、适合向量检索的查询语句。"
    "规则：1.解析代词指代（如"它"、"这个"、"上面提到的"），替换为具体实体名称；"
    "2.补全省略的主语或宾语；3.去除口语化，使用书面语；"
    "4.如果问题已经独立完整，直接返回原问题。"
    "只输出改写后的问题，不要解释，不要加任何前缀。"
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

    async def rewrite_query(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        if not history:
            rewritten = await self._llm_service.generate(
                prompt=question, system=_REWRITE_SYSTEM
            )
            return rewritten.strip() or question

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _REWRITE_SYSTEM}
        ]
        messages.extend(history[-10:])
        messages.append({
            "role": "user",
            "content": f"请结合以上对话历史，将下面这个问题改写为独立的检索查询：\n{question}",
        })
        rewritten = await self._llm_service.chat(messages)
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
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        rewritten = await self.rewrite_query(question, history=history)

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
