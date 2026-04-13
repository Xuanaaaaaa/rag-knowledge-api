from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import aiofiles
import fitz  # PyMuPDF
from docx import Document as DocxDocument

from app.config import Settings
from app.core.chunker import split_text
from app.core.embedder import get_embeddings
from app.core.vectorstore import VectorStore


def _compute_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


async def _extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        def _parse_pdf() -> str:
            doc = fitz.open(stream=content, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)

        return await asyncio.to_thread(_parse_pdf)

    elif suffix in (".docx", ".doc"):
        def _parse_docx() -> str:
            import io
            doc = DocxDocument(io.BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs if para.text.strip())

        return await asyncio.to_thread(_parse_docx)

    else:
        return content.decode("utf-8", errors="ignore")


class DocumentService:
    def __init__(self, settings: Settings, vectorstore: VectorStore) -> None:
        self._settings = settings
        self._vectorstore = vectorstore

    async def ingest(
        self,
        filename: str,
        content: bytes,
        collection_name: str = "default",
    ) -> dict[str, Any]:
        doc_id = _compute_md5(content)

        # 覆盖旧版本：先删除同 doc_id 的旧 chunks
        await self._vectorstore.delete_by_doc_id(collection_name, doc_id)

        # 解析文本
        text = await _extract_text(filename, content)

        # 分块
        chunks = split_text(text, self._settings.chunk_size, self._settings.chunk_overlap)
        if not chunks:
            return {"doc_id": doc_id, "filename": filename, "chunk_count": 0}

        # 向量化
        embeddings = await get_embeddings(
            chunks,
            model=self._settings.ollama_embed_model,
            base_url=self._settings.ollama_base_url,
        )

        # 构建 metadata
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "source_path": filename,
            }
            for i in range(len(chunks))
        ]

        # 入库
        await self._vectorstore.add_chunks(
            collection_name=collection_name,
            doc_id=doc_id,
            chunks=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return {"doc_id": doc_id, "filename": filename, "chunk_count": len(chunks)}

    async def list_documents(self, collection_name: str = "default") -> list[dict[str, Any]]:
        return await self._vectorstore.list_documents(collection_name)

    async def delete_document(self, doc_id: str, collection_name: str = "default") -> None:
        await self._vectorstore.delete_by_doc_id(collection_name, doc_id)
