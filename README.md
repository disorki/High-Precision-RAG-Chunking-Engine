# Intelligent RAG System

AI-powered Knowledge Base with PDF upload, RAG-based retrieval, and streaming chat interface.

![Tech Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat&logoColor=white)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, LangChain, SQLAlchemy |
| Database | PostgreSQL 16 + pgvector |
| AI/LLM | Ollama (nomic-embed-text, mistral) |
| Frontend | Next.js 14, TailwindCSS, react-pdf |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU (optional, for faster Ollama inference)

### 1. Clone and Setup

```bash
cd "c:\High-Precision RAG Chunking Engine"

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Pull required Ollama models (first time only)
docker exec -it rag-ollama ollama pull nomic-embed-text
docker exec -it rag-ollama ollama pull mistral
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
├── docker-compose.yml          # Container orchestration
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── init.sql                # PostgreSQL init (pgvector)
│   └── app/
│       ├── main.py             # FastAPI entry point
│       ├── config.py           # Settings
│       ├── database.py         # SQLAlchemy setup
│       ├── models/             # Database models
│       ├── schemas/            # Pydantic schemas
│       ├── routers/            # API endpoints
│       ├── services/           # RAG pipeline, retrieval
│       └── workers/            # Background tasks
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    └── src/
        ├── app/                # Next.js App Router
        └── components/         # React components
```

## API Endpoints

### Upload
- `POST /api/upload` - Upload PDF document
- `GET /api/documents` - List all documents
- `GET /api/documents/{id}` - Get document status
- `DELETE /api/documents/{id}` - Delete document

### Chat
- `POST /api/chat` - Chat with document (SSE streaming)
- `GET /api/chat/sessions` - List chat sessions
- `GET /api/chat/sessions/{id}` - Get session with messages

## Features

- **PDF Processing**: Upload PDFs, automatic text extraction and chunking
- **Vector Search**: pgvector-powered similarity search using cosine distance
- **Streaming Chat**: Real-time responses via Server-Sent Events
- **Source Citations**: View which document sections were used for answers
- **PDF Viewer**: Built-in PDF viewer with zoom and navigation

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Model for embeddings (768 dims) |
| `CHAT_MODEL` | `mistral` | Model for chat responses |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |

## Development

### Run without Docker

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Troubleshooting

### Ollama GPU Issues
If using CPU-only, remove the `deploy.resources` section from `docker-compose.yml`.

### Database Connection
Ensure PostgreSQL is running and pgvector extension is enabled:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## License

MIT
