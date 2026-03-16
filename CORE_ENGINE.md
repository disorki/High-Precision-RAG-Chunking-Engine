# RAG Core Engine Documentation

This document provides a deep technical overview of the system's "engine". It is intended for DevOps engineers and system architects.

## 1. System Architecture

The system is built on the classic **Retrieval-Augmented Generation (RAG)** architecture with full local execution of all components.

### Key Components:
1.  **FastAPI Backend**: Coordinates all processes, manages business logic, and exposes the API.
2.  **RAG Pipeline**: Responsible for text extraction, chunking, and embedding generation.
3.  **Vector Database (PostgreSQL + pgvector)**: Stores and enables semantic search of text chunks.
4.  **Ollama**: Local LLM server for generating embeddings and model inferences.
5.  **Reranker (Cross-Encoder)**: Optional layer for refining search results.

---

## 2. Document Processing Pipeline (`rag_pipeline.py`)

The service transforms raw files into structured vector data.

### Processing Stages:
1.  **Text Extraction**:
    *   **PDF**: Handled via `pypdf`. Supports multi-page documents.
    *   **DOCX**: Parses paragraphs and tables. Tables are converted to Markdown-like text to preserve structure.
    *   **XLSX**: Each sheet is processed as a separate table.
    *   **TXT**: Direct reading with encoding auto-detection (UTF-8, CP1251).
2.  **Chunking**:
    *   Uses `RecursiveCharacterTextSplitter`.
    *   **Size (chunk_size)**: 1500 characters (configurable).
    *   **Overlap (overlap)**: 300 characters to maintain context between blocks.
    *   **Separators**: `\n\n`, `\n`, `. `, ` ` (in descending order of priority).
3.  **Embedding Generation**:
    *   Default model: `nomic-embed-text` (via Ollama).
    *   Parallel chunk processing (configurable concurrency via `embedding_concurrency`).
    *   Retry mechanism for Ollama service availability.

---

## 3. Retrieval and Reranking (`retrieval.py` & `reranker.py`)

These services ensure the most relevant data is found for the user's query.

### Retrieval Process:
1.  **Vector Search**:
    *   User query is converted into an embedding.
    *   Search is performed in PostgreSQL using cosine distance (`<=>`).
    *   **Similarity Threshold**: Default is 0.05.
2.  **Reranking**:
    *   If enabled (`enable_reranker=True`), uses a Cross-Encoder model (e.g., `ms-marco-MiniLM-L-6-v2`).
    *   The Cross-Encoder evaluates the actual relevance of the "Query-Chunk" pair, which is significantly more accurate than standard vector search.
3.  **Context Assembly**:
    *   Top-K chunks (default 20) are combined into a single string.
    *   Source metadata (filename, page number) is added.
    *   Context limit: 16000 tokens.

---

## 4. Configuration (DevOps Manual)

### Environment Variables (.env)
| Variable | Description | Default Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `OLLAMA_BASE_URL` | Ollama server address | `http://localhost:11434` |
| `EMBEDDING_MODEL` | Model for vector embeddings | `nomic-embed-text` |
| `CHAT_MODEL` | Generation model (RAG) | `qwen2.5:7b` |
| `AGENT_MODEL` | Model for the Agent | `qwen2.5:14b` |
| `CHUNK_SIZE` | Text block size | `1500` |
| `TOP_K_CHUNKS` | Number of chunks in context | `20` |
| `ENABLE_RERANKER`| Use Cross-Encoder | `false` |

### Deployment Recommendations:
1.  **GPU Acceleration**: NVIDIA GPU is highly recommended for Ollama. Ensure `deploy.resources.reservations.devices` is configured in Docker-compose.
2.  **DB Optimization**: Ensure the `vector` extension is installed in PostgreSQL. For large datasets (100k+ chunks), creating an `HNSW` or `IVFFlat` index is recommended.
3.  **Scalability**: The backend is stateless. Multiple replicas can be run behind a load balancer.

---

## 5. Yandex.Disk Integration (`yandex_disk.py`)

*   Operates via **OAuth 2.0**.
*   **Synchronization**: Compares hashes of local and cloud files.
*   **Automation**: Background update check mechanism (configurable interval).
*   **Import**: Files are downloaded, registered in the DB, and automatically sent to the RAG pipeline.

---

## 6. Agent Logic (`agent_chat.py`)

The Agent follows a **Native RAG** approach:
1.  **Query Analysis**: LLM determines needed data (global search vs. document-specific).
2.  **Reasoning**: Forms an internal search plan.
3.  **Synthesis**: Processes chunks, analyzes them, and generates an answer with strict page references (`[Page X]`).
4.  **Safety**: If no data is found, the agent must report this instead of hallucinating.
