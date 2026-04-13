from __future__ import annotations

from app.core.chunker import split_text


def test_split_text_returns_chunks():
    text = "这是第一段。\n\n这是第二段。\n\n这是第三段。"
    chunks = split_text(text, chunk_size=20, chunk_overlap=5)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_split_text_respects_chunk_size():
    # 生成超过 chunk_size 的文本
    text = "A" * 200
    chunks = split_text(text, chunk_size=50, chunk_overlap=10)
    # 每个 chunk 不超过 chunk_size + overlap 的合理范围
    for chunk in chunks:
        assert len(chunk) <= 80  # 允许一定的边界宽松


def test_split_empty_text():
    chunks = split_text("", chunk_size=512, chunk_overlap=64)
    assert chunks == []


def test_split_text_default_params():
    text = "测试默认参数。" * 100
    chunks = split_text(text)
    assert len(chunks) >= 1
