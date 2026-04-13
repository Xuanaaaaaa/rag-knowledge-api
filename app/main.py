from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import documents, query
from app.config import get_settings
from app.exceptions import AppException
from app.models import ErrorResponse, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 启动时检查 Ollama 连通性（非阻塞，仅日志）
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
        print(f"[startup] Ollama connected at {settings.ollama_base_url}")
    except Exception as e:
        print(f"[startup] WARNING: Ollama not reachable: {e}")
    yield


app = FastAPI(
    title="RAG 知识库问答 API",
    version="1.0.0",
    description="本地知识库问答服务，支持 PDF / Word / txt 文档上传和流式问答",
    lifespan=lifespan,
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.error,
            message=exc.message,
            status_code=exc.status_code,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message=str(exc),
            status_code=500,
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
        ollama_ok = True
    except Exception:
        ollama_ok = False

    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        ollama_connected=ollama_ok,
        message="服务运行正常" if ollama_ok else "Ollama 不可达，请检查服务状态",
    )


app.include_router(documents.router)
app.include_router(query.router)
