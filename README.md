# 🌐 English | [Русский](README.ru.md)

# High-Precision RAG Chunking Engine
A specialized RAG (Retrieval-Augmented Generation) system designed for detailed technical documentation. It features **smart table-aware chunking**, **strict source citations**, and a **streaming chat interface** with context awareness.

![Tech Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat&logoColor=white)

## key Features

### 🧠 High-Precision RAG
- **Table-Aware Chunking**: Preserves Markdown tables and data structures during ingestion.
- **Smart Context Retrieval**: Filters chunks by relevance threshold and sorts them by document order for coherent reading.
- **Strict Citations**: Every fact in the response is cited with `[Page X]` references.
- **Query Rewriting**: Automatically converts conversational questions (e.g., "what about memory?") into precise technical search queries.

### 💬 Advanced Chat
- **Streaming Responses**: Real-time token streaming via Server-Sent Events (SSE).
- **History Compression**: Automatically summarizes/truncates old chat history to maintain infinite conversation within context limits.
- **Context Window**: Optimized for large contexts (up to 16k tokens) to handle complex docs.

### 🛠 Technical Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, LangChain.
- **Vector DB**: PostgreSQL 16 with `pgvector` extension.
- **LLM Engine**: Ollama (running locally).
  - Embeddings: `nomic-embed-text`
  - Chat: `mistral` (tunable)
- **Frontend**: Next.js 14, TailwindCSS, Lucide Icons.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (for running LLMs locally)

### 1. Installation

```bash
# Clone repository
git clone https://github.com/disorki/High-Precision-RAG-Chunking-Engine.git
cd "High-Precision RAG Chunking Engine"

# Setup environment files
# (Copy .env.example if available, or create new ones)
```

### 2. Run with Docker

```bash
# Build and start services
docker-compose up --build
```

The system needs to pull LLM models on first run. Open a separate terminal:
```bash
docker exec -it rag-ollama ollama pull nomic-embed-text
docker exec -it rag-ollama ollama pull mistral
```

### 3. Access

- **Frontend (Chat & Upload)**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs

## Configuration (`backend/.env`)

You can tune the RAG pipeline and model parameters without changing code:

### Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | DB Connection |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Internal Ollama URL |
| `UPLOAD_DIR` | `/app/uploads` | Path for PDF storage |

### RAG Tuning
| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `1500` | Larger text blocks to keep tables intact |
| `CHUNK_OVERLAP` | `300` | Overlap to prevent context loss at boundaries |
| `TOP_K_CHUNKS` | `10` | Number of chunks to retrieve initially |
| `SIMILARITY_THRESHOLD`| `0.3` | Min. cosine similarity (0.0-1.0) to filter noise |

### Chat Model Parameters
| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MODEL` | `mistral` | LLM model name to use |
| `CHAT_TEMPERATURE` | `0.3` | Creativity (0.0 = strict, 1.0 = creative) |
| `CHAT_NUM_CTX` | `16384` | Context window size (tokens) |
| `CONTEXT_MAX_TOKENS` | `6000` | Max tokens used for retrieved documents |
| `HISTORY_MAX_CHARS` | `3000` | Limit for past conversation history |

## Usage Guide

1. **Upload**: Go to the main page and upload a PDF document (e.g., a technical manual).
2. **Wait**: The system will extract text, chunk it, and generate vector embeddings (status: "Processing" -> "Ready").
3. **Chat**: Click on the document card to open the chat.
   - Ask specific questions: *"What is the max voltage for port A?"*
   - ask general summaries: *"List all safety warnings."*
   - The system will answer with citations `[Page 12]`.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── routers/       # chat.py, upload.py
│   │   ├── services/      # rag_pipeline.py, retrieval.py
│   │   ├── models/        # SQLAlchemy DB models
│   │   └── config.py      # Pydantic settings
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # ChatInterface, UploadZone
│   │   └── app/           # Next.js pages
│   └── Dockerfile
└── docker-compose.yml
```

## License
MIT
