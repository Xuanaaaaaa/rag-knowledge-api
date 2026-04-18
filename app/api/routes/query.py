from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.core.vectorstore import VectorStore
from app.models import ChatMessage, QueryRequest, QueryResponse, SourceReference
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/v1/query", tags=["query"])

_ANSWER_SYSTEM = (
    "你是一个知识库问答助手。请根据提供的参考文档内容回答用户的问题。"
    "如果参考内容不足以回答，请如实说明。回答要简洁、准确。"
)


def _build_answer_messages(
    question: str,
    context_chunks: list[dict],
    history: list[ChatMessage],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": _ANSWER_SYSTEM}]
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    context = "\n\n".join(
        f"[文档 {i+1}] {c['document']}" for i, c in enumerate(context_chunks)
    )
    messages.append({
        "role": "user",
        "content": f"参考文档：\n{context}\n\n用户问题：{question}",
    })
    return messages


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
    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
    rewritten, sources = await service.retrieve(
        request.question,
        collection_name=request.collection_name,
        history=history_dicts,
    )
    messages = _build_answer_messages(request.question, sources, request.history)
    llm = LLMService(base_url=settings.ollama_base_url, model=settings.ollama_model)
    answer = await llm.chat(messages)

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
    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]
    rewritten, sources = await service.retrieve(
        request.question,
        collection_name=request.collection_name,
        history=history_dicts,
    )
    messages = _build_answer_messages(request.question, sources, request.history)

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
        async for token in llm.chat_stream(messages):
            payload = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        sources_payload = json.dumps(
            {"type": "sources", "content": source_refs}, ensure_ascii=False
        )
        yield f"data: {sources_payload}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")
