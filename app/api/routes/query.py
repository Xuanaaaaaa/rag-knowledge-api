from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.core.vectorstore import VectorStore
from app.models import QueryRequest, QueryResponse, SourceReference
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/v1/query", tags=["query"])

_ANSWER_SYSTEM = (
    "你是一个知识库问答助手。请根据提供的参考文档内容回答用户的问题。"
    "如果参考内容不足以回答，请如实说明。回答要简洁、准确。"
)


def _build_prompt(question: str, context_chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[文档 {i+1}] {c['document']}" for i, c in enumerate(context_chunks)
    )
    return f"参考文档：\n{context}\n\n用户问题：{question}"


def _get_retrieval_service(settings: Settings = Depends(get_settings)) -> RetrievalService:
    vectorstore = VectorStore(settings.chroma_persist_dir)
    llm_service = LLMService(base_url=settings.ollama_base_url, model=settings.ollama_model)
    return RetrievalService(settings=settings, vectorstore=vectorstore, llm_service=llm_service)


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: RetrievalService = Depends(_get_retrieval_service),
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    rewritten, sources = await service.retrieve(
        request.question, collection_name=request.collection_name
    )
    prompt = _build_prompt(request.question, sources)
    llm = LLMService(base_url=settings.ollama_base_url, model=settings.ollama_model)
    answer = await llm.generate(prompt=prompt, system=_ANSWER_SYSTEM)

    source_refs = [
        SourceReference(
            file=s["metadata"].get("filename", ""),
            chunk_index=s["metadata"].get("chunk_index", 0),
            score=s.get("rerank_score", 0.0),
        )
        for s in sources
    ]

    return QueryResponse(answer=answer, sources=source_refs, rewritten_query=rewritten)


@router.post("/stream")
async def query_stream(
    request: QueryRequest,
    service: RetrievalService = Depends(_get_retrieval_service),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    rewritten, sources = await service.retrieve(
        request.question, collection_name=request.collection_name
    )
    prompt = _build_prompt(request.question, sources)

    source_refs = [
        {
            "file": s["metadata"].get("filename", ""),
            "chunk": s["metadata"].get("chunk_index", 0),
            "score": round(s.get("rerank_score", 0.0), 4),
        }
        for s in sources
    ]

    llm = LLMService(base_url=settings.ollama_base_url, model=settings.ollama_model)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for token in llm.generate_stream(prompt=prompt, system=_ANSWER_SYSTEM):
            payload = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        sources_payload = json.dumps(
            {"type": "sources", "content": source_refs}, ensure_ascii=False
        )
        yield f"data: {sources_payload}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")
