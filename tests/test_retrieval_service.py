from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.retrieval_service import RetrievalService


def _make_service() -> RetrievalService:
    from app.config import Settings
    settings = Settings(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
        ollama_embed_model="nomic-embed-text",
        top_k_retrieve=10,
        top_k_rerank=3,
    )
    mock_vectorstore = MagicMock()
    mock_llm = MagicMock()
    return RetrievalService(settings=settings, vectorstore=mock_vectorstore, llm_service=mock_llm)


@pytest.mark.asyncio
async def test_rewrite_query_returns_string():
    service = _make_service()
    service._llm_service.generate = AsyncMock(return_value="改写后的查询")

    result = await service.rewrite_query("啥是 RAG")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_rerank_selects_top_k():
    service = _make_service()

    candidates = [
        {"document": f"文档内容 {i}", "metadata": {"filename": "test.pdf", "chunk_index": i}, "distance": 0.1 * i}
        for i in range(10)
    ]

    with patch("app.services.retrieval_service.FlagReranker") as mock_reranker_cls:
        mock_reranker = MagicMock()
        mock_reranker.compute_score = MagicMock(
            return_value=[[0.9 - i * 0.05 for i in range(10)]]
        )
        mock_reranker_cls.return_value = mock_reranker

        result = service.rerank("测试查询", candidates, top_k=3)

    assert len(result) == 3


@pytest.mark.asyncio
async def test_retrieve_returns_sources():
    service = _make_service()
    service._llm_service.generate = AsyncMock(return_value="改写查询")

    mock_embedding = [0.1] * 384
    mock_candidates = [
        {"document": "相关内容", "metadata": {"filename": "doc.pdf", "chunk_index": 0}, "distance": 0.1}
        for _ in range(3)
    ]

    with patch("app.services.retrieval_service.get_embeddings", return_value=[mock_embedding]):
        with patch("app.services.retrieval_service.FlagReranker") as mock_reranker_cls:
            mock_reranker = MagicMock()
            mock_reranker.compute_score = MagicMock(return_value=[[0.9, 0.8, 0.7]])
            mock_reranker_cls.return_value = mock_reranker

            service._vectorstore.query = AsyncMock(return_value=mock_candidates)

            rewritten, sources = await service.retrieve("测试问题", collection_name="default")

    assert rewritten == "改写查询"
    assert len(sources) <= 3
    assert all("document" in s for s in sources)
