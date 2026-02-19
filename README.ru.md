# [English](README.md) | Русский

# High-Precision RAG Chunking Engine

Специализированная RAG-система (Retrieval-Augmented Generation) для работы с технической документацией. Включает умный чанкинг с сохранением таблиц, строгое цитирование источников, двухэтапную генерацию ответов с переводом и потоковый чат-интерфейс с контекстной памятью.

![Tech Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat&logoColor=white)

## Ключевые возможности

### Высокоточный RAG
- **Table-Aware Chunking** -- сохраняет таблицы и структуры данных при разбиении текста.
- **Умный поиск контекста** -- фильтрует чанки по порогу релевантности и сортирует в порядке документа.
- **Строгое цитирование** -- каждый факт сопровождается ссылкой `[Стр. X]`.
- **Переформулировка запросов** -- превращает разговорные вопросы в точные поисковые запросы.

### Продвинутый чат
- **Двухэтапная генерация** -- модель сначала формирует ответ на английском (максимальное качество), затем переводит на язык пользователя.
- **Потоковые ответы** -- токены приходят в реальном времени через SSE.
- **Сжатие истории** -- автоматическое управление контекстным окном для длительных диалогов.
- **Контекстное окно** -- до 16k токенов для обработки сложных документов.

### Поддерживаемые форматы
- PDF
- Word (.docx) -- с корректным порядком таблиц и текста
- Excel (.xlsx)
- Текстовые файлы (.txt) -- автоопределение кодировки (UTF-8, CP1251, Latin-1)

### Отказоустойчивость
- **Проверка Ollama** -- перед обработкой документа проверяется доступность сервиса и наличие модели.
- **Retry с backoff** -- повторные попытки генерации эмбеддингов при временных сбоях (3 попытки с экспоненциальной задержкой).
- **Проверка при старте** -- при запуске сервера логируется статус Ollama и доступность моделей.

### Технологический стек
- **Бэкенд**: Python 3.11, FastAPI, SQLAlchemy, LangChain.
- **Векторная БД**: PostgreSQL 16 + расширение `pgvector`.
- **LLM-движок**: Ollama (локальный запуск).
  - Эмбеддинги: `nomic-embed-text`
  - Чат-модель: `mistral` (настраивается)
- **Фронтенд**: Next.js 14, TailwindCSS, Lucide Icons.

## Быстрый старт

### Требования
- Docker и Docker Compose
- 8 ГБ+ оперативной памяти
- NVIDIA GPU (рекомендуется, но не обязательно)

### 1. Установка

```bash
git clone https://github.com/disorki/High-Precision-RAG-Chunking-Engine.git
cd "High-Precision RAG Chunking Engine"
```

### 2. Запуск через Docker

```bash
docker-compose up --build
```

При первом запуске нужно скачать модели:
```bash
docker exec -it rag-ollama ollama pull nomic-embed-text
docker exec -it rag-ollama ollama pull mistral
```

### 3. Поддержка GPU (NVIDIA)

GPU-ускорение включено по умолчанию в `docker-compose.yml`. Если у вас нет NVIDIA GPU, закомментируйте секцию `deploy` в сервисе `ollama`.

Для работы GPU требуется:
- Драйверы NVIDIA
- Docker Desktop с WSL2-движком
- NVIDIA Container Toolkit

### 4. Доступ

- **Фронтенд (чат и загрузка)**: http://localhost:3000
- **API документация**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## Конфигурация (`backend/.env`)

### Основные настройки
| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `postgresql://...` | Подключение к БД |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL Ollama (внутренний) |
| `UPLOAD_DIR` | `/app/uploads` | Путь хранения файлов |

### Настройки RAG
| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `CHUNK_SIZE` | `1500` | Размер чанков (больше -- таблицы целиком) |
| `CHUNK_OVERLAP` | `300` | Перекрытие чанков |
| `TOP_K_CHUNKS` | `10` | Количество чанков для поиска |
| `SIMILARITY_THRESHOLD` | `0.3` | Мин. косинусное сходство (0.0--1.0) |
| `EMBEDDING_RETRY_COUNT` | `3` | Количество повторных попыток генерации эмбеддингов |
| `EMBEDDING_RETRY_DELAY` | `1.0` | Базовая задержка (сек) для exponential backoff |

### Параметры чат-модели
| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `CHAT_MODEL` | `mistral` | Модель для ответов |
| `CHAT_TEMPERATURE` | `0.3` | Креативность (0.0 = строго, 1.0 = свободно) |
| `CHAT_NUM_CTX` | `16384` | Размер контекстного окна (токены) |
| `CONTEXT_MAX_TOKENS` | `6000` | Макс. токенов для контекста из документа |
| `HISTORY_MAX_CHARS` | `3000` | Лимит символов для истории чата |

## Как пользоваться

1. **Загрузите** документ (PDF, DOCX, XLSX или TXT) на главной странице.
2. **Подождите** обработку -- система извлечет текст, разобьет на чанки, проверит Ollama и создаст эмбеддинги. Прогресс отображается в реальном времени.
3. **Задайте вопрос** в чате:
   - Конкретный: *"Какое максимальное напряжение на порту A?"*
   - Общий: *"Перечисли все предупреждения по безопасности"*
   - Система ответит на вашем языке со ссылками `[Стр. 12]`.
4. **Управление** -- документы можно удалять кнопкой в списке. При ошибке обработки отображаются подробности.

## Структура проекта

```
backend/
  app/
    routers/        # chat.py, upload.py
    services/       # rag_pipeline.py, retrieval.py
    workers/        # document_processor.py
    models/         # SQLAlchemy модели БД
    config.py       # Pydantic настройки
  Dockerfile
frontend/
  src/
    components/     # ChatInterface, UploadZone, DocumentList, FileViewer
    app/            # Next.js страницы
  Dockerfile
docker-compose.yml
```

## Лицензия
MIT
