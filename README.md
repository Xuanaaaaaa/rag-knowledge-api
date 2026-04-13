# RAG 知识库问答 API

本地知识库问答服务，支持 PDF / Word / txt 文档上传、向量化入库和流式问答。**全程本地运行，数据不出本机。**

---

## 目录

- [项目架构](#项目架构)
- [技术选型与理由](#技术选型与理由)
- [核心流程详解](#核心流程详解)
- [RAG 优化策略](#rag-优化策略)
- [关键技术实现](#关键技术实现)
- [快速开始](#快速开始)
- [API 接口](#api-接口)
- [配置说明](#配置说明)
- [运行测试](#运行测试)

---

## 项目架构

### 目录结构

```
rag-knowledge-api/
├── app/
│   ├── main.py                       # FastAPI 入口：路由注册、lifespan、全局异常处理
│   ├── config.py                     # 统一配置（Pydantic BaseSettings，读取 .env）
│   ├── models.py                     # 所有 Request / Response Pydantic Schema
│   ├── exceptions.py                 # 自定义异常类 AppException
│   ├── api/
│   │   └── routes/
│   │       ├── documents.py          # 文档管理接口（上传 / 列出 / 删除）
│   │       └── query.py              # 问答接口（普通 JSON + SSE 流式）
│   ├── services/
│   │   ├── document_service.py       # 文档处理流水线（解析→分块→向量化→入库）
│   │   ├── retrieval_service.py      # RAG 检索（查询改写→向量检索→Reranker重排序）
│   │   └── llm_service.py            # Ollama LLM 调用封装（流式 + 非流式）
│   └── core/
│       ├── chunker.py                # 文本分块（RecursiveCharacterTextSplitter）
│       ├── embedder.py               # Embedding 生成（调用 Ollama /api/embed）
│       └── vectorstore.py            # ChromaDB 封装（async 安全的增删查）
├── tests/
│   ├── test_chunker.py               # 分块逻辑单元测试
│   ├── test_embedder.py              # Embedding 接口单元测试（mock Ollama）
│   └── test_retrieval_service.py     # 检索服务单元测试（mock 所有外部依赖）
├── .env.example                      # 配置模板
├── requirements.txt                  # 依赖清单
└── README.md
```

### 层次关系

```
HTTP 请求
    │
    ▼
[API 路由层]  documents.py / query.py
    │  负责参数校验、权限判断、响应格式化
    ▼
[服务层]  DocumentService / RetrievalService / LLMService
    │  负责业务逻辑编排，不直接接触 HTTP
    ▼
[核心层]  chunker / embedder / vectorstore
    │  负责单一技术能力：分块、向量化、存取
    ▼
[外部依赖]  Ollama（LLM + Embedding）/ ChromaDB（向量持久化）
```

---

## 技术选型与理由

| 组件 | 选型 | 核心理由 |
|------|------|---------|
| API 框架 | **FastAPI** | 原生 `async/await`，Pydantic v2 自动校验，自动生成 OpenAPI 文档 |
| 向量数据库 | **ChromaDB** | 纯本地文件持久化，无需额外服务进程，Python 原生接口 |
| Embedding 模型 | **nomic-embed-text**（Ollama） | 与 LLM 共用同一套 Ollama 管理，无需额外部署 |
| LLM | **Ollama**（模型可配置） | 支持任意本地模型，默认 qwen2.5:7b |
| 文档解析 | **PyMuPDF + python-docx** | 覆盖 PDF / Word / txt 三种主要格式 |
| 文本分块 | **RecursiveCharacterTextSplitter** | 按语义边界递归切割，优于固定窗口切割 |
| 重排序 | **BGE Reranker**（BAAI/bge-reranker-base） | Cross-encoder 精度远高于向量余弦相似度 |
| 包管理 | **uv** | 安装速度快，与其他项目保持一致 |

---

## 核心流程详解

### 文档入库流程

```
用户上传文件（PDF / docx / txt）
        │
        ▼
  计算文件内容 MD5 → 作为 doc_id
        │
        ▼  （若已存在则先删除旧 chunks，实现幂等覆盖）
  格式检测 → 解析纯文本
  · PDF:   PyMuPDF 逐页提取文字
  · docx:  python-docx 提取段落文本
  · txt:   UTF-8 直接解码
        │
        ▼
  RecursiveCharacterTextSplitter 分块
  chunk_size=512, overlap=64
  分隔符优先级: \n\n > \n > 。！？ > 空格 > 字符
        │
        ▼
  批量调用 Ollama nomic-embed-text 生成向量
        │
        ▼
  写入 ChromaDB（单一 collection，metadata 含 doc_id / filename / chunk_index）
        │
        ▼
  返回 {doc_id, filename, chunk_count}
```

**chunk_size=512 的理由**：约等于 300-400 个中文字，能容纳一个完整语义段落，又不会携带过多噪声稀释向量语义。`overlap=64` 防止跨 chunk 边界的语义断裂。

### 问答流程

```
用户提问（原始自然语言）
        │
        ▼
【第一步：查询改写】
  用 LLM 将口语化问题改写为向量检索友好的表达
  · 去除语气词、补全隐含主语
  · 拆解复合问题为单一意图
        │
        ▼
  调用 Ollama nomic-embed-text 对改写后问题生成向量
        │
        ▼
  ChromaDB 向量相似度检索，取 Top-10 候选 chunk
        │
        ▼
【第二步：BGE Reranker 精排】
  Cross-encoder 对 (查询, chunk) 逐对打分
  取 Top-3 高分 chunk
        │
        ▼
  组装 Prompt：system 提示 + Top-3 context + 原始问题
        │
        ▼
  调用 Ollama LLM 生成回答（流式输出）
        │
        ▼
  SSE 推送 token 流，附带来源引用（文件名 + chunk 编号 + 得分）
```

---

## RAG 优化策略

### 为什么需要查询改写？

用户的自然语言问题往往口语化，含有指代词、省略主语或复合意图，直接向量化后检索效果差。改写步骤将问题规范化，使其更贴近文档中的表达方式。

示例：
- 原始：`"它的主要优势是什么？"`
- 改写：`"nomic-embed-text 的主要技术优势是什么？"`

### 为什么用两阶段检索？

| 阶段 | 方法 | 特点 |
|------|------|------|
| 粗检索 | 向量余弦相似度（Top-10） | 速度快，召回率高，但精度有限 |
| 精排 | BGE Reranker cross-encoder（Top-3） | 速度慢但精度高，对语义理解更深 |

两阶段设计：用粗检索快速缩小候选范围（从全库→10条），再用精排保证质量（10条→3条），兼顾性能与精度。

### BGE Reranker 工作原理

Cross-encoder 将查询和文档**拼接**后一起送入模型，输出一个相关性得分，而非分别编码再比较距离。代价是无法预计算文档向量，但对语义理解的精度远超双编码器模型。

---

## 关键技术实现

### 1. 异步安全的 ChromaDB 封装

ChromaDB 的 Python 客户端是**同步阻塞**接口，直接在 `async` 函数中调用会阻塞 FastAPI 的事件循环。解决方案是用 `asyncio.to_thread()` 将同步调用委托到线程池：

```python
# app/core/vectorstore.py
async def add_chunks(self, ...) -> None:
    def _add() -> None:          # 同步操作
        col = self._get_or_create_collection(collection_name)
        col.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)

    await asyncio.to_thread(_add)  # 在线程池执行，不阻塞事件循环
```

### 2. doc_id 使用文件内容 MD5

```python
# app/services/document_service.py
def _compute_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()
```

同一文件无论上传多少次，`doc_id` 不变。入库前先删除旧 chunks 再重新写入，实现**幂等覆盖**，数据库中永远不会有重复数据。

### 3. BGE Reranker 进程级单例

Reranker 模型加载耗时约 2-5 秒，用模块级变量缓存实例，只在首次调用时初始化：

```python
# app/services/retrieval_service.py
_reranker_instance: FlagReranker | None = None

def _get_reranker() -> FlagReranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = FlagReranker("BAAI/bge-reranker-base", use_fp16=True)
    return _reranker_instance
```

`use_fp16=True` 在 Apple Silicon / CUDA 设备上减半显存占用，推理速度提升约 2 倍。

### 4. SSE 流式输出

问答接口使用 `StreamingResponse` 逐 token 推送，响应格式为标准 Server-Sent Events：

```python
# app/api/routes/query.py
async def event_generator() -> AsyncGenerator[str, None]:
    async for token in llm.generate_stream(prompt=prompt, system=_ANSWER_SYSTEM):
        payload = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
        yield f"data: {payload}\n\n"

    yield f"data: {json.dumps({'type': 'sources', 'content': source_refs})}\n\n"
    yield 'data: {"type": "done"}\n\n'
```

最后推送 `sources`（来源引用）和 `done` 信号，前端可据此展示引用并关闭连接。

### 5. 统一错误处理

所有业务异常通过 `AppException` 抛出，FastAPI `exception_handler` 统一格式化返回，避免各路由散落 `try/except`：

```python
# app/exceptions.py
class AppException(Exception):
    def __init__(self, error: str, message: str, status_code: int = 400) -> None:
        self.error = error
        self.message = message
        self.status_code = status_code
```

响应格式固定：
```json
{"error": "unsupported_file_type", "message": "不支持的文件类型 .pptx", "status_code": 400}
```

### 6. 依赖版本注意事项

`FlagEmbedding >= 1.2.0` 依赖 `transformers < 5.0.0`。transformers 5.x 移除了 `is_torch_fx_available`，会导致导入失败。`requirements.txt` 已锁定：

```
transformers>=4.30.0,<5.0.0
```

---

## 快速开始

### 1. 准备 Ollama 模型

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### 2. 创建虚拟环境并安装依赖

```bash
uv venv
uv pip install -r requirements.txt
```

> 首次运行会从 HuggingFace 自动下载 BGE Reranker 模型（约 1GB），之后完全本地运行。

### 3. 配置环境变量

```bash
cp .env.example .env
# 按需修改 .env 中的模型名称或路径
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看交互式 API 文档。

---

## API 接口

### 健康检查

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "ollama_connected": true, "message": "服务运行正常"}
```

### 上传文档

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@report.pdf"
```

```json
{"doc_id": "a3f1c2...", "filename": "report.pdf", "chunk_count": 42, "message": "文档已成功索引"}
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

```json
{
  "answer": "根据文档内容，核心概念包括...",
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

```
data: {"type": "token", "content": "根"}
data: {"type": "token", "content": "据"}
...
data: {"type": "sources", "content": [{"file": "report.pdf", "chunk": 3, "score": 0.92}]}
data: {"type": "done"}
```

---

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 生成模型（可替换为任意 Ollama 支持的模型） |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding 模型 |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB 持久化目录 |
| `TOP_K_RETRIEVE` | `10` | 向量检索候选数（粗检索） |
| `TOP_K_RERANK` | `3` | Reranker 重排序后保留数（精排） |
| `CHUNK_SIZE` | `512` | 分块大小（字符数） |
| `CHUNK_OVERLAP` | `64` | 相邻分块重叠字符数 |

---

## 运行测试

```bash
pytest tests/ -v
```

测试覆盖三个核心模块，所有外部依赖（Ollama、ChromaDB）均通过 mock 隔离：

| 测试文件 | 测试内容 | 用例数 |
|---------|---------|--------|
| `test_chunker.py` | 分块逻辑、边界条件、空文本处理 | 4 |
| `test_embedder.py` | Ollama API 调用封装、批量输入 | 2 |
| `test_retrieval_service.py` | 查询改写、Reranker 重排序、完整检索流程 | 3 |
