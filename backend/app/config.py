import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ragdb"
    
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    
    # Upload settings
    upload_dir: str = "./uploads"
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    
    # RAG settings
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen2.5:7b"
    chunk_size: int = 1500  # Larger chunks for tables
    chunk_overlap: int = 300  # More overlap to avoid splitting tables
    top_k_chunks: int = 10  # Retrieve more chunks for better context
    vector_dimensions: int = 768  # nomic-embed-text dimension
    
    # Chat model parameters (tunable via .env)
    chat_temperature: float = 0.3
    chat_num_ctx: int = 16384
    chat_top_k: int = 50
    chat_top_p: float = 0.9
    similarity_threshold: float = 0.3  # Minimum cosine similarity to include chunk
    context_max_tokens: int = 6000  # Max tokens for context window
    history_max_chars: int = 3000  # Max chars for chat history
    
    # Advanced Retrieval Features
    enable_context_headers: bool = True  # LLM generates "context headers" for chunks
    embedding_concurrency: int = 5       # Max parallel embedding requests
    embedding_cache_size: int = 1000     # LRU cache size for embeddings
    enable_reranker: bool = True         # Use cross-encoder for reranking results
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 5              # Items to keep after reranking

    # Agent settings
    agent_model: str = "qwen2.5:7b"      # Model used by Flowise agent tools
    agent_max_iterations: int = 8         # Max ReAct reasoning iterations
    agent_summarize_chunks: int = 5       # Chunks used for document summarization

    # Retry settings
    embedding_retry_count: int = 3
    embedding_retry_delay: float = 1.0  # Base delay in seconds (exponential backoff)
    
    # Yandex Disk Integration (OAuth)
    yandex_client_id: str = ""  # OAuth app Client ID
    yandex_client_secret: str = ""  # OAuth app Client Secret
    sync_default_interval: int = 30  # Default sync interval in minutes
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
