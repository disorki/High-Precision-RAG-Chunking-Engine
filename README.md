# English | [Русский](README.ru.md)

# High-Precision RAG Chunking Engine

A specialized RAG (Retrieval-Augmented Generation) system for technical documentation. Features smart table-aware chunking, strict source citations, two-step answer generation with translation, and a streaming chat interface with conversation memory.

![Tech Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat&logoColor=white)

## Key Features

### High-Precision RAG
- **Table-Aware Chunking** -- preserves Markdown tables and data structures during ingestion.
- **Smart Context Retrieval** -- filters chunks by relevance threshold and sorts by document order.
- **Strict Citations** -- every fact is cited with `[Page X]` references.
- **Query Rewriting** -- automatically converts conversational questions into precise search queries.

### Advanced Chat
- **Two-Step Generation** -- the model first generates an answer in English (best reasoning quality), then translates to the user's language.
- **Streaming Responses** -- real-time token streaming via Server-Sent Events (SSE).
- **History Compression** -- automatically manages context window for long conversations.
- **Large Context Window** -- optimized for up to 16k tokens.

### Supported File Formats
- PDF
- Word (.docx) -- tables and paragraphs extracted in correct document order
- Excel (.xlsx)
- Plain text (.txt) -- auto-detects encoding (UTF-8, CP1251, Latin-1)

### Fault Tolerance
- **Ollama Pre-Check** -- verifies service availability and model presence before processing.
- **Retry with Backoff** -- retries embedding generation on transient failures (3 attempts with exponential delay).
- **Startup Health Check** -- logs Ollama status and model availability on server start.

### Technical Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, LangChain.
- **Vector DB**: PostgreSQL 16 with `pgvector` extension.
- **LLM Engine**: Ollama (running locally).
  - Embeddings: `nomic-embed-text`
  - Chat: `mistral` (configurable)
- **Frontend**: Next.js 14, TailwindCSS, Lucide Icons.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- 8GB+ RAM
- NVIDIA GPU (recommended, not required)

### 1. Installation

```bash
git clone https://github.com/disorki/High-Precision-RAG-Chunking-Engine.git
cd "High-Precision RAG Chunking Engine"
```

### 2. Run with Docker

```bash
docker-compose up --build
```

Pull the LLM models on first run:
```bash
docker exec -it rag-ollama ollama pull nomic-embed-text
docker exec -it rag-ollama ollama pull mistral
```

### 3. GPU Support (NVIDIA)

GPU acceleration is enabled by default in `docker-compose.yml`. If you don't have an NVIDIA GPU, comment out the `deploy` section under the `ollama` service.

Requirements for GPU support:
- NVIDIA drivers
- Docker Desktop with WSL2 engine
- NVIDIA Container Toolkit

### 4. Access

- **Frontend (Chat and Upload)**: http://localhost:3000
- **Backend API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## Configuration (`backend/.env`)

### Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | Database connection |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Internal Ollama URL |
| `UPLOAD_DIR` | `/app/uploads` | File storage path |

### RAG Tuning
| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `1500` | Chunk size (larger keeps tables intact) |
| `CHUNK_OVERLAP` | `300` | Overlap to prevent context loss at boundaries |
| `TOP_K_CHUNKS` | `10` | Number of chunks to retrieve |
| `SIMILARITY_THRESHOLD` | `0.3` | Min. cosine similarity (0.0--1.0) |
| `EMBEDDING_RETRY_COUNT` | `3` | Retry attempts for embedding generation |
| `EMBEDDING_RETRY_DELAY` | `1.0` | Base delay (seconds) for exponential backoff |

### Chat Model Parameters
| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MODEL` | `mistral` | LLM model name |
| `CHAT_TEMPERATURE` | `0.3` | Creativity (0.0 = strict, 1.0 = creative) |
| `CHAT_NUM_CTX` | `16384` | Context window size (tokens) |
| `CONTEXT_MAX_TOKENS` | `6000` | Max tokens for retrieved context |
| `HISTORY_MAX_CHARS` | `3000` | Limit for past conversation history |

## Usage

1. **Upload** a document (PDF, DOCX, XLSX, or TXT) on the main page.
2. **Wait** for processing -- the system extracts text, chunks it, verifies Ollama, and generates embeddings. Progress is shown in real time.
3. **Chat** with the document:
   - Specific: *"What is the max voltage for port A?"*
   - General: *"List all safety warnings."*
   - The system responds in your language with page citations `[Page 12]`.
4. **Manage** -- documents can be deleted from the list. Failed documents show detailed error messages.

## Project Structure

```
backend/
  app/
    routers/        # chat.py, upload.py
    services/       # rag_pipeline.py, retrieval.py
    workers/        # document_processor.py
    models/         # SQLAlchemy DB models
    config.py       # Pydantic settings
  Dockerfile
frontend/
  src/
    components/     # ChatInterface, UploadZone, DocumentList, FileViewer
    app/            # Next.js pages
  Dockerfile
docker-compose.yml
```

## License
MIT
