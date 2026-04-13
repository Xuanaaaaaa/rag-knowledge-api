from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx


class LLMService:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url
        self._model = model

    async def generate(self, prompt: str, system: str = "") -> str:
        """非流式生成，返回完整文本。"""
        url = f"{self._base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("response", "")

    async def generate_stream(
        self, prompt: str, system: str = ""
    ) -> AsyncGenerator[str, None]:
        """流式生成，逐 token yield。"""
        import json

        url = f"{self._base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            break
