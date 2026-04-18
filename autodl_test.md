# RAG 知识库问答 API — 演示测试完整操作指南

> 适用场景：已完成首次环境搭建，新开 AutoDL 终端后从零恢复服务并完成完整演示测试。

---

## 前置条件（已完成，无需重复）

- Ollama 二进制已安装至 `/usr/local/bin/ollama`
- 模型 `nomic-embed-text` 和 `qwen2.5:7b` 已拉取
- BGE Reranker 模型已缓存至本地（`~/.cache/huggingface/`）
- 项目代码已克隆至 `/root/autodl-tmp/rag-knowledge-api`
- Python 依赖已安装至项目虚拟环境 `.venv`

---

## 一、启动 Ollama 服务

新开终端后，Ollama 服务不会自动启动，需要手动重启。

```bash
# 检查 Ollama 是否已在运行（有输出则跳过启动步骤）
pgrep ollama

# 若未运行，启动 Ollama（带代理，用于保持网络连通性）
HTTP_PROXY=http://172.32.52.144:12798 \
HTTPS_PROXY=http://172.32.52.144:12798 \
OLLAMA_HOST=0.0.0.0 \
nohup ollama serve > /root/ollama.log 2>&1 &

# 等待服务就绪
sleep 3

# 验证服务正常
curl http://localhost:11434
# 预期输出：Ollama is running
```

---

## 二、启动 FastAPI 服务

```bash
# 进入项目目录
cd /root/autodl-tmp/rag-knowledge-api

# 激活虚拟环境
source .venv/bin/activate

# 设置 HuggingFace 镜像（BGE Reranker 从本地缓存加载，此项防止联网超时报错）
export HF_ENDPOINT=https://hf-mirror.com

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

看到以下输出表示启动成功：

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

> **注意**：首次加载 BGE Reranker 模型时终端会打印下载/加载日志，属于正常现象，等待约 30 秒即可。

---

## 三、配置本地 SSH 隧道（在本地电脑执行）

在**本地电脑**终端运行以下命令，将 AutoDL 实例端口映射到本地：

```bash
ssh -L 8000:localhost:8000 -p 20788 root@connect.bjb1.seetacloud.com
```

连接成功后，本地浏览器访问：

```
http://localhost:8000/docs
```

可看到 Swagger UI 交互式文档界面，说明服务完全可用。

---

## 四、演示测试流程

以下所有 `curl` 命令在 **AutoDL 终端**（新开一个 tab）中执行。

### 4.1 健康检查

```bash
curl http://localhost:8000/health
```

预期返回：

```json
{"status": "ok", "ollama_connected": true, "message": "服务运行正常"}
```

---

### 4.2 准备测试文档

```bash
echo "人工智能是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。机器学习是人工智能的核心技术之一，通过数据驱动的方式让计算机自动学习和改进。深度学习是机器学习的子领域，基于多层神经网络实现复杂的模式识别任务。" > test.txt
```

---

### 4.3 上传文档

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@test.txt"
```

预期返回：

```json
{
  "doc_id": "xxxxxxxxxxxxxxxx",
  "filename": "test.txt",
  "chunk_count": 1,
  "message": "文档已成功索引"
}
```

---

### 4.4 列出已索引文档

```bash
curl http://localhost:8000/api/v1/documents
```

---

### 4.5 普通问答

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是机器学习？"}'
```

预期返回（含来源引用和查询改写）：

```json
{
  "answer": "机器学习是人工智能的一个核心技术，通过数据驱动的方式让计算机自动学习和改进。",
  "sources": [{"file": "test.txt", "chunk_index": 0, "score": 0.93}],
  "rewritten_query": "什么是机器学习技术？"
}
```

---

### 4.6 流式问答（SSE）

```bash
curl -N -X POST http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "深度学习和机器学习有什么区别？"}'
```

预期返回逐 token 流式输出：

```
data: {"type": "token", "content": "深"}
data: {"type": "token", "content": "度"}
...
data: {"type": "sources", "content": [{"file": "test.txt", "chunk": 0, "score": 0.91}]}
data: {"type": "done"}
```

---

### 4.7 删除文档

```bash
# 将 doc_id 替换为 4.3 步骤中返回的实际值
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id}
```

---

## 五、运行单元测试

```bash
cd /root/autodl-tmp/rag-knowledge-api
source .venv/bin/activate
python -m pytest tests/ -v
```

预期结果：

```
tests/test_chunker.py::test_split_text_returns_chunks        PASSED
tests/test_chunker.py::test_split_text_respects_chunk_size   PASSED
tests/test_chunker.py::test_split_empty_text                 PASSED
tests/test_chunker.py::test_split_text_default_params        PASSED
tests/test_embedder.py::test_get_embeddings_returns_vectors  PASSED
tests/test_embedder.py::test_get_embeddings_multiple_texts   PASSED
tests/test_retrieval_service.py::test_rewrite_query_returns_string  PASSED
tests/test_retrieval_service.py::test_rerank_selects_top_k   PASSED
tests/test_retrieval_service.py::test_retrieve_returns_sources      PASSED

9 passed in 5.68s
```

---

## 六、常见问题排查

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `curl http://localhost:11434` 无响应 | Ollama 服务未启动 | 执行第一节启动命令 |
| 问答请求超时无返回 | Ollama 推理进程崩溃 | `kill $(pgrep ollama)` 后重启 |
| BGE 模型加载时 timeout 警告 | HF 镜像 HEAD 请求超时，但本地缓存可用 | 忽略警告，服务正常运行 |
| `command not found: pytest` | 虚拟环境未激活 | `source .venv/bin/activate` |
| 服务启动报 `SyntaxError` | 中文引号导致字符串语法错误 | 参考初次部署时的修复步骤 |

---

## 七、服务架构速查

```
用户请求
   │
   ▼
FastAPI（端口 8000）
   │
   ├── 文档上传 → PyMuPDF/python-docx 解析 → 分块(512字符) → nomic-embed-text 向量化 → ChromaDB 存储
   │
   └── 问答请求 → 查询改写(LLM) → 向量检索 Top-10 → BGE Reranker 精排 Top-3 → LLM 生成回答 → SSE 流式输出
```

---

*生成时间：2026-04-18*