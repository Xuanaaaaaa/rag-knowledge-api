from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    chroma_persist_dir: str = "./chroma_db"
    top_k_retrieve: int = 10
    top_k_rerank: int = 3
    chunk_size: int = 512
    chunk_overlap: int = 64

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
