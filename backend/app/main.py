import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import httpx

from app.database import engine, Base
from app.routers import upload_router, chat_router, search_router, index_router, sync_router, agent_chat_router
from app.config import get_settings

# логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


def run_migrations():
    # запуск миграций alembic
    try:
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as e:
        logger.warning(f"Alembic migration failed: {e}")


async def check_ollama_on_startup():
    # проверка связи с ollama при запуске
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/version")
            if resp.status_code == 200:
                version = resp.json().get("version", "unknown")
                logger.info(f"Ollama connected: version {version}")
            else:
                logger.warning(f"Ollama responded with status {resp.status_code}")
                return
    except Exception as e:
        logger.warning(
            f"Ollama is not reachable at {settings.ollama_base_url}: {e}"
        )
        return

    # проверка доступности моделей
    for model_name in [settings.embedding_model, settings.chat_model]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/show",
                    json={"name": model_name}
                )
                if resp.status_code == 200:
                    logger.info(f"Model '{model_name}' is available")
                else:
                    logger.warning(
                        f"Model '{model_name}' not found"
                    )
        except Exception as e:
            logger.warning(f"⚠️ Could not check model '{model_name}': {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # управление жизненным циклом приложения
    logger.info("Starting RAG API server...")
    
    # запуск миграций бд
    run_migrations()
    
    # создание папки для загрузок
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info(f"Upload directory: {settings.upload_dir}")
    
    # проверка ollama
    await check_ollama_on_startup()
    
    # запуск планировщика синхронизации
    try:
        from app.workers.sync_scheduler import init_scheduler, register_all_sources, stop_scheduler
        init_scheduler()
        register_all_sources()
    except Exception as e:
        logger.warning(f"Failed to start sync scheduler: {e}")
    
    yield
    
    # остановка сервисов при выключении
    try:
        from app.workers.sync_scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    logger.info("Shutting down RAG API server...")


# инициализация fastapi
app = FastAPI(
    title="Intelligent RAG System",
    description="AI-powered Knowledge Base with PDF upload and chat",
    version="1.0.0",
    lifespan=lifespan
)

# настройка cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id", "X-Sources"]
)

# подключение роутеров
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(index_router)
app.include_router(sync_router)
app.include_router(agent_chat_router)

# статика для pdf
if os.path.exists(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/")
async def root():
    # корневой эндпоинт
    return {
        "name": "Intelligent RAG System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    # проверка состояния систем
    ollama_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/version")
            ollama_status = "connected" if resp.status_code == 200 else f"error ({resp.status_code})"
    except Exception:
        ollama_status = "unreachable"

    return {
        "status": "healthy",
        "database": "connected",
        "ollama_url": settings.ollama_base_url,
        "ollama_status": ollama_status,
        "embedding_model": settings.embedding_model,
        "chat_model": settings.chat_model
    }
