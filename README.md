# RAG 知识库问答 API

本地知识库问答服务，支持 PDF / Word / txt 文档上传和流式问答。全程本地运行，数据不出本机。

## 技术栈

- **API**: FastAPI + uvicorn
- **向量库**: ChromaDB（本地持久化）
- **Embedding**: nomic-embed-text（via Ollama）
- **LLM**: Ollama（默认 qwen2.5:7b，可配置）
- **重排序**: BGE Reranker (BAAI/bge-reranker-base)

## 快速开始

### 1. 准备 Ollama 模型

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### 2. 安装依赖

```bash
uv venv
uv pip install -r requirements.txt
```

> 首次运行会从 HuggingFace 自动下载 BGE Reranker 模型（约 1GB），之后完全本地运行。

### 3. 配置环境

```bash
cp .env.example .env
# 按需修改 .env 中的模型名称
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看交互式 API 文档。

## API 接口

### 健康检查

```bash
curl http://localhost:8000/health
```

### 上传文档

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@report.pdf"
```

响应：
```json
{"doc_id": "a3f1...", "filename": "report.pdf", "chunk_count": 42, "message": "文档已成功索引"}
```

### 列出文档

```bash
curl http://localhost:8000/api/v1/documents
```

### 删除文档

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id}
```

### 普通问答

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "文档中提到了哪些核心概念？"}'
```

响应：
```json
{
  "answer": "根据文档内容...",
  "sources": [{"file": "report.pdf", "chunk_index": 3, "score": 0.92}],
  "rewritten_query": "文档中的核心概念有哪些"
}
```

### 流式问答（SSE）

```bash
curl -N -X POST http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "文档中提到了哪些核心概念？"}'
```

响应流：
```
data: {"type": "token", "content": "根"}
data: {"type": "token", "content": "据"}
...
data: {"type": "sources", "content": [{"file": "report.pdf", "chunk": 3, "score": 0.92}]}
data: {"type": "done"}
```

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| OLLAMA_BASE_URL | http://localhost:11434 | Ollama 服务地址 |
| OLLAMA_MODEL | qwen2.5:7b | 生成模型 |
| OLLAMA_EMBED_MODEL | nomic-embed-text | Embedding 模型 |
| CHROMA_PERSIST_DIR | ./chroma_db | ChromaDB 持久化目录 |
| TOP_K_RETRIEVE | 10 | 向量检索候选数 |
| TOP_K_RERANK | 3 | 重排序后保留数 |
| CHUNK_SIZE | 512 | 分块大小（字符数） |
| CHUNK_OVERLAP | 64 | 分块重叠（字符数） |

## 运行测试

```bash
pytest tests/ -v
```
