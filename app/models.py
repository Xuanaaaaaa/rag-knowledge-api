from __future__ import annotations

from pydantic import BaseModel


# ---- Document ----

class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    message: str


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    source_path: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DeleteDocumentResponse(BaseModel):
    doc_id: str
    message: str


# ---- Query ----

class QueryRequest(BaseModel):
    question: str
    collection_name: str = "default"


class SourceReference(BaseModel):
    file: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    rewritten_query: str


# ---- Health ----

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    message: str


# ---- Error ----

class ErrorResponse(BaseModel):
    error: str
    message: str
    status_code: int
