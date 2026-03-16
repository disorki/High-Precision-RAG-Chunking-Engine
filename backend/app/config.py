import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # настройки приложения из .env
    
    # база данных
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ragdb"
    
    # ollama
    ollama_base_url: str = "http://localhost:11434"
    
    # загрузки
    upload_dir: str = "./uploads"
    max_file_size: int = 50 * 1024 * 1024  # 50мб
    
    # настройки rag
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen2.5:7b"
    chunk_size: int = 1500  # размер чанка (увеличено для таблиц)
    chunk_overlap: int = 300  # перекрытие
    top_k_chunks: int = 20  # количество чанков для контекста
    vector_dimensions: int = 768  # размерность nomic
    
    # параметры чата
    chat_temperature: float = 0.15
    chat_num_ctx: int = 16384
    chat_top_k: int = 50
    chat_top_p: float = 0.9
    similarity_threshold: float = 0.05  # порог сходства
    context_max_tokens: int = 16000  # лимит токенов контекста
    history_max_chars: int = 3000  # лимит истории чата
    
    # продвинутый поиск
    enable_context_headers: bool = True  # заголовки контекста для llm
    embedding_concurrency: int = 5       # параллельные запросы эмбеддингов
    embedding_cache_size: int = 1000     # размер кэша эмбеддингов
    enable_reranker: bool = False         # реранкер (отключен для скорости)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 12              # топ после реранкинга

    # настройки агента
    agent_model: str = "qwen2.5:14b"      # модель агента
    agent_max_iterations: int = 8         # макс итераций react
    agent_summarize_chunks: int = 5       # чанков для саммари

    # повторы запросов
    embedding_retry_count: int = 3
    embedding_retry_delay: float = 1.0
    
    # яндекс диск (oauth)
    yandex_client_id: str = ""  # id клиента
    yandex_client_secret: str = ""  # секрет
    sync_default_interval: int = 30  # интервал синхронизации (мин)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    # кэшированный экземпляр настроек
    return Settings()
