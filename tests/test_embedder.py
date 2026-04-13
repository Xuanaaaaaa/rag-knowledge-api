from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.embedder import get_embeddings


@pytest.mark.asyncio
async def test_get_embeddings_returns_vectors():
    mock_response = {
        "embeddings": [[0.1, 0.2, 0.3] * 128]  # 384-dim mock
    }
    with patch("app.core.embedder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            return_value=AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
        )
        mock_client_cls.return_value = mock_client

        result = await get_embeddings(["测试文本"], model="nomic-embed-text", base_url="http://localhost:11434")

    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0]) == 384


@pytest.mark.asyncio
async def test_get_embeddings_multiple_texts():
    mock_response = {
        "embeddings": [[0.1] * 384, [0.2] * 384]
    }
    with patch("app.core.embedder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            return_value=AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
        )
        mock_client_cls.return_value = mock_client

        result = await get_embeddings(
            ["文本一", "文本二"],
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )

    assert len(result) == 2
