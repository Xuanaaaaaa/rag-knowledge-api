# RAG 知识库问答 API 接口文档

**版本：** 1.0.0  
**Base URL：** `http://localhost:8000`  
**文档日期：** 2026-04-15

---

## 目录

1. [概述](#1-概述)
2. [通用说明](#2-通用说明)
3. [接口列表](#3-接口列表)
   - [健康检查](#31-健康检查)
   - [上传文档](#32-上传文档)
   - [获取文档列表](#33-获取文档列表)
   - [删除文档](#34-删除文档)
   - [普通问答](#35-普通问答)
   - [流式问答](#36-流式问答-sse)
4. [数据模型](#4-数据模型)
5. [错误处理](#5-错误处理)
6. [前端集成示例](#6-前端集成示例)

---

## 1. 概述

本服务是一个基于本地大语言模型（Ollama）的知识库问答系统（RAG）。  
前端可通过以下流程使用服务：

```
上传文档 → 建立知识库索引 → 向知识库提问 → 获取 AI 回答（含来源引用）
```

支持的功能：
- 上传 PDF / Word（.docx / .doc）/ 纯文本（.txt）文档并自动建立向量索引
- 列出已索引的文档
- 删除已索引的文档
- 基于知识库内容进行问答（支持普通响应和 SSE 流式响应）

---

## 2. 通用说明

### 请求格式

| 类型 | 说明 |
|------|------|
| 文件上传 | `multipart/form-data` |
| 其余请求体 | `application/json` |

### 响应格式

所有响应均为 JSON 格式（流式接口除外，详见 [流式问答](#36-流式问答-sse)）。

### 状态码

| HTTP 状态码 | 含义 |
|-------------|------|
| `200` | 请求成功 |
| `400` | 请求参数错误（如文件类型不支持） |
| `404` | 资源不存在（如文档 ID 不存在） |
| `500` | 服务器内部错误 |

---

## 3. 接口列表

### 3.1 健康检查

检查服务及底层 Ollama 大模型服务是否正常运行。

**请求**

```
GET /health
```

**请求参数：** 无

**响应示例**

```json
{
  "status": "ok",
  "ollama_connected": true,
  "message": "服务运行正常"
}
```

**Ollama 不可达时的响应示例**

```json
{
  "status": "degraded",
  "ollama_connected": false,
  "message": "Ollama 不可达，请检查服务状态"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `string` | `"ok"` 表示完全正常，`"degraded"` 表示 Ollama 服务异常 |
| `ollama_connected` | `boolean` | Ollama 是否连通 |
| `message` | `string` | 人类可读的状态描述 |

---

### 3.2 上传文档

上传一个文档文件，服务端会自动解析、分块并建立向量索引。

**请求**

```
POST /api/v1/documents
Content-Type: multipart/form-data
```

**请求参数**

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `file` | form-data | `File` | 是 | 要上传的文档文件，支持 `.pdf` / `.docx` / `.doc` / `.txt` |

**响应示例（200）**

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "产品手册.pdf",
  "chunk_count": 42,
  "message": "文档已成功索引"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `string` | 文档的唯一标识符（UUID），后续删除文档时使用 |
| `filename` | `string` | 上传的文件名 |
| `chunk_count` | `number` | 文档被切分成的段落数量 |
| `message` | `string` | 操作结果描述 |

**错误响应示例（400）**

```json
{
  "error": "unsupported_file_type",
  "message": "不支持的文件类型 .xlsx，仅支持 PDF / docx / txt",
  "status_code": 400
}
```

---

### 3.3 获取文档列表

获取当前知识库中所有已索引文档的列表。

**请求**

```
GET /api/v1/documents
```

**请求参数：** 无

**响应示例（200）**

```json
{
  "documents": [
    {
      "doc_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "产品手册.pdf",
      "chunk_count": 42,
      "source_path": "./uploads/产品手册.pdf"
    },
    {
      "doc_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "filename": "用户协议.txt",
      "chunk_count": 15,
      "source_path": "./uploads/用户协议.txt"
    }
  ],
  "total": 2
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `documents` | `array` | 文档信息列表 |
| `documents[].doc_id` | `string` | 文档唯一标识符 |
| `documents[].filename` | `string` | 文件名 |
| `documents[].chunk_count` | `number` | 切分段落数 |
| `documents[].source_path` | `string` | 服务端存储路径（仅供参考） |
| `total` | `number` | 文档总数 |

---

### 3.4 删除文档

从知识库中删除指定文档及其所有向量索引。

**请求**

```
DELETE /api/v1/documents/{doc_id}
```

**路径参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `doc_id` | `string` | 是 | 文档的唯一标识符（来自上传响应或文档列表） |

**响应示例（200）**

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "文档已删除"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `string` | 被删除文档的唯一标识符 |
| `message` | `string` | 操作结果描述 |

---

### 3.5 普通问答

向知识库提问，返回完整的回答及引用来源（一次性返回全部内容）。

**请求**

```
POST /api/v1/query
Content-Type: application/json
```

**请求体**

```json
{
  "question": "产品的退款政策是什么？",
  "collection_name": "default"
}
```

**请求字段说明**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | `string` | 是 | — | 用户提问内容 |
| `collection_name` | `string` | 否 | `"default"` | 知识库集合名称，用于区分不同的文档集合 |

**响应示例（200）**

```json
{
  "answer": "根据产品手册第 3 章，退款政策如下：购买后 7 天内可申请全额退款，需提供购买凭证...",
  "sources": [
    {
      "file": "产品手册.pdf",
      "chunk_index": 12,
      "score": 0.9231
    },
    {
      "file": "产品手册.pdf",
      "chunk_index": 13,
      "score": 0.8745
    }
  ],
  "rewritten_query": "产品退款政策及流程"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | `string` | AI 生成的回答内容 |
| `sources` | `array` | 回答所引用的文档片段列表 |
| `sources[].file` | `string` | 来源文件名 |
| `sources[].chunk_index` | `number` | 在文档中的段落序号（从 0 开始） |
| `sources[].score` | `number` | 相关度评分（0～1，越高越相关） |
| `rewritten_query` | `string` | 经过 AI 改写后的查询语句（供调试参考） |

> **注意：** 此接口需等待 AI 完整生成回答后才返回，响应时间取决于回答长度，通常为 5～30 秒。对于需要实时展示打字效果的场景，建议使用 [流式问答接口](#36-流式问答-sse)。

---

### 3.6 流式问答（SSE）

向知识库提问，以 [Server-Sent Events（SSE）](https://developer.mozilla.org/zh-CN/docs/Web/API/Server-sent_events) 方式实时流式返回 AI 回答，支持逐字打字效果。

**请求**

```
POST /api/v1/query/stream
Content-Type: application/json
```

**请求体（与普通问答相同）**

```json
{
  "question": "产品的退款政策是什么？",
  "collection_name": "default"
}
```

**请求字段说明**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | `string` | 是 | — | 用户提问内容 |
| `collection_name` | `string` | 否 | `"default"` | 知识库集合名称 |

**响应格式**

响应的 `Content-Type` 为 `text/event-stream`，每条事件格式如下：

```
data: <JSON 字符串>\n\n
```

服务端会依次发送三种类型的事件：

#### 事件类型 1：`token`（回答文本片段）

回答生成过程中，持续发送多个 `token` 事件，每个事件包含一小段文本。

```
data: {"type": "token", "content": "根据"}

data: {"type": "token", "content": "产品"}

data: {"type": "token", "content": "手册"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `string` | 固定为 `"token"` |
| `content` | `string` | 当前文本片段，需拼接所有 token 得到完整回答 |

#### 事件类型 2：`sources`（引用来源，回答结束后发送一次）

```
data: {"type": "sources", "content": [{"file": "产品手册.pdf", "chunk": 12, "score": 0.9231}, {"file": "产品手册.pdf", "chunk": 13, "score": 0.8745}]}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `string` | 固定为 `"sources"` |
| `content` | `array` | 引用来源列表 |
| `content[].file` | `string` | 来源文件名 |
| `content[].chunk` | `number` | 段落序号 |
| `content[].score` | `number` | 相关度评分（已四舍五入为 4 位小数） |

#### 事件类型 3：`done`（流结束标志）

```
data: {"type": "done"}
```

收到此事件后，表示本次问答流式传输已完全结束。

**完整 SSE 流示例**

```
data: {"type": "token", "content": "根据"}
data: {"type": "token", "content": "产品手册第 3 章"}
data: {"type": "token", "content": "，退款政策如下"}
data: {"type": "token", "content": "：购买后 7 天内可申请全额退款..."}
data: {"type": "sources", "content": [{"file": "产品手册.pdf", "chunk": 12, "score": 0.9231}]}
data: {"type": "done"}
```

---

## 4. 数据模型

### DocumentUploadResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `string` | 文档唯一标识符（UUID） |
| `filename` | `string` | 文件名 |
| `chunk_count` | `number` | 切分段落数 |
| `message` | `string` | 操作描述 |

### DocumentInfo

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `string` | 文档唯一标识符 |
| `filename` | `string` | 文件名 |
| `chunk_count` | `number` | 切分段落数 |
| `source_path` | `string` | 服务端存储路径 |

### DocumentListResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `documents` | `DocumentInfo[]` | 文档列表 |
| `total` | `number` | 总数 |

### DeleteDocumentResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `string` | 被删除文档的 ID |
| `message` | `string` | 操作描述 |

### QueryRequest

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | `string` | 是 | — | 问题内容 |
| `collection_name` | `string` | 否 | `"default"` | 集合名称 |

### QueryResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | `string` | AI 回答 |
| `sources` | `SourceReference[]` | 引用来源 |
| `rewritten_query` | `string` | 改写后的查询 |

### SourceReference

| 字段 | 类型 | 说明 |
|------|------|------|
| `file` | `string` | 来源文件名 |
| `chunk_index` | `number` | 段落序号 |
| `score` | `number` | 相关度评分 |

### HealthResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `string` | `"ok"` 或 `"degraded"` |
| `ollama_connected` | `boolean` | Ollama 连通状态 |
| `message` | `string` | 状态描述 |

### ErrorResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| `error` | `string` | 错误码（英文标识符） |
| `message` | `string` | 人类可读的错误描述 |
| `status_code` | `number` | HTTP 状态码 |

---

## 5. 错误处理

所有非 2xx 响应均返回统一的 `ErrorResponse` 结构：

```json
{
  "error": "错误码",
  "message": "错误描述",
  "status_code": 400
}
```

**常见错误码**

| `error` 字段值 | HTTP 状态码 | 触发场景 |
|----------------|------------|---------|
| `unsupported_file_type` | `400` | 上传了不支持的文件类型 |
| `internal_server_error` | `500` | 服务端未预期的异常 |

---

## 6. 前端集成示例

### 6.1 上传文档（JavaScript / Fetch API）

```javascript
async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/v1/documents', {
    method: 'POST',
    body: formData,
    // 注意：使用 FormData 时不要手动设置 Content-Type，浏览器会自动添加 boundary
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.message);
  }

  return await response.json();
  // 返回 { doc_id, filename, chunk_count, message }
}
```

### 6.2 普通问答（JavaScript / Fetch API）

```javascript
async function query(question, collectionName = 'default') {
  const response = await fetch('http://localhost:8000/api/v1/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, collection_name: collectionName }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.message);
  }

  return await response.json();
  // 返回 { answer, sources, rewritten_query }
}
```

### 6.3 流式问答（JavaScript / EventSource 方案）

> **注意：** 由于标准 `EventSource` 仅支持 GET 请求，流式问答（POST 请求）需使用 `fetch` 手动处理 SSE，或使用 [`@microsoft/fetch-event-source`](https://github.com/Azure/fetch-event-source) 等库。

```javascript
async function queryStream(question, collectionName = 'default', onToken, onSources, onDone) {
  const response = await fetch('http://localhost:8000/api/v1/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, collection_name: collectionName }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.message);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // 保留不完整的一行

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const json = line.slice(6).trim();
      if (!json) continue;

      const event = JSON.parse(json);

      if (event.type === 'token') {
        onToken(event.content);           // 追加文字到界面
      } else if (event.type === 'sources') {
        onSources(event.content);         // 展示引用来源
      } else if (event.type === 'done') {
        onDone();                          // 流结束，隐藏加载状态
      }
    }
  }
}

// 使用示例
let fullAnswer = '';

await queryStream(
  '退款政策是什么？',
  'default',
  (token) => {
    fullAnswer += token;
    document.getElementById('answer').textContent = fullAnswer;
  },
  (sources) => {
    console.log('引用来源：', sources);
  },
  () => {
    console.log('回答完毕');
  }
);
```

### 6.4 删除文档（JavaScript / Fetch API）

```javascript
async function deleteDocument(docId) {
  const response = await fetch(`http://localhost:8000/api/v1/documents/${docId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.message);
  }

  return await response.json();
  // 返回 { doc_id, message }
}
```

---

*接口文档由后端团队维护，如有变更请同步更新此文档。*
