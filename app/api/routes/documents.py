from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile

from app.config import Settings, get_settings
from app.core.vectorstore import VectorStore
from app.exceptions import AppException
from app.models import (
    DeleteDocumentResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt"}


def _get_document_service(settings: Settings = Depends(get_settings)) -> DocumentService:
    vectorstore = VectorStore(settings.chroma_persist_dir)
    return DocumentService(settings=settings, vectorstore=vectorstore)


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    service: DocumentService = Depends(_get_document_service),
) -> DocumentUploadResponse:
    from pathlib import Path

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise AppException(
            error="unsupported_file_type",
            message=f"不支持的文件类型 {suffix}，仅支持 PDF / docx / txt",
            status_code=400,
        )

    content = await file.read()
    result = await service.ingest(filename=file.filename or "unknown", content=content)

    return DocumentUploadResponse(
        doc_id=result["doc_id"],
        filename=result["filename"],
        chunk_count=result["chunk_count"],
        message="文档已成功索引",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentService = Depends(_get_document_service),
) -> DocumentListResponse:
    docs = await service.list_documents()
    items = [
        DocumentInfo(
            doc_id=d.get("doc_id", ""),
            filename=d.get("filename", ""),
            chunk_count=0,
            source_path=d.get("source_path", ""),
        )
        for d in docs
    ]
    return DocumentListResponse(documents=items, total=len(items))


@router.delete("/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    doc_id: str,
    service: DocumentService = Depends(_get_document_service),
) -> DeleteDocumentResponse:
    await service.delete_document(doc_id)
    return DeleteDocumentResponse(doc_id=doc_id, message="文档已删除")
