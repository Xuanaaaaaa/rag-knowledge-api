from __future__ import annotations

import httpx


async def get_embeddings(
    texts: list[str],
    model: str,
    base_url: str,
) -> list[list[float]]:
    """调用 Ollama /api/embed 接口批量生成向量。"""
    url = f"{base_url}/api/embed"
    payload = {"model": model, "input": texts}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["embeddings"]
