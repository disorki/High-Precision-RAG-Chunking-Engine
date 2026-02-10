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
    chat_model: str = "mistral"
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
