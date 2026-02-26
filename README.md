# High-Precision RAG Chunking Engine & Flowise AI Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)

> *Read this documentation in [Russian (Русский)](README.ru.md)*

A modern, high-precision Retrieval-Augmented Generation (RAG) system engineered for deep analytical document processing. The system features an integrated **Flowise ReAct AI Agent** and ensures complete data privacy through **fully local processing** using **Ollama** (powered by Qwen 2.5).

Designed for complex data extraction, synthesis, and analysis across texts, tables, and scanned document formats.

---

## Enterprise-Grade Features

*   **Autonomous AI Agent (Flowise Integration)**
    *   Embedded ReAct (Reasoning and Acting) agent architecture.
    *   Dynamic, autonomous tool selection to handle complex, multi-step user queries.
*   **Comprehensive RAG Toolchain (7 Specialized Modules)**
    1.  `search_all`: Global semantic vector search across the entire document repository.
    2.  `search_document`: Targeted contextual search within a specified document.
    3.  `list_documents`: Real-time retrieval of the loaded document index.
    4.  `get_document_info`: Comprehensive temporal and structural metadata analysis.
    5.  `summarize`: Advanced AI abstraction and summarization of massive text corpora.
    6.  `compare_documents`: Cross-document fact-checking and comparative analysis.
    7.  `extract_facts`: Precision data point extraction and structural mapping.
*   **Seamless Cloud Integration**
    *   Native Yandex.Disk integration via secure OAuth 2.0.
    *   Automated synchronization and batch importation of files and directories.
*   **Advanced Processing Pipeline**
    *   Supports: `PDF` (with full OCR via Tesseract/EasyOCR), `DOCX`, `XLSX`, and `TXT`.
    *   Automated extraction and indexing of ZIP and RAR archives with batch processing capabilities.
*   **Premium UI/UX Ecosystem**
    *   Built on Next.js 14 and React.
    *   Modern aesthetic: Glassmorphism, Dark Mode, and Lucide iconography.
*   **Zero-Trust Local Environment**
    *   100% on-premise execution.
    *   All telemetry, document data, and LLM inferences (via Ollama) remain strictly local. No exposure to external vendor APIs (OpenAI, Anthropic, etc.).

---

## System Architecture

The application is distributed across four robust microservices, seamlessly orchestrated via Docker:

1.  **Frontend Module (`:3000`)**
    *   *Tech Stack:* Next.js App Router, React, Tailwind CSS.
    *   *Role:* Delivers the interactive upload interface, spatial cloud management (Yandex.Disk), and the real-time embedded Agent Chat client.
2.  **Backend Core (`:8000`)**
    *   *Tech Stack:* FastAPI (Python), LangChain, unstructured.
    *   *Role:* Orchestrates the ingestion pipeline—parsing, advanced chunking (Semantic + Sliding Window overlay), embedding generation, vector database routing, and exposing RESTful API adapters for Flowise tool consumption.
3.  **Flowise Orchestrator (`:3001`)**
    *   *Role:* Visual pipeline constructor acting as the cognitive engine for the ReAct agent, maintaining stateful conversational context (BufferMemory).
4.  **Database & Inference Layer**
    *   `PostgreSQL + pgvector` (`:5432`): Persistent storage for document chunks and high-dimensional vector embeddings.
    *   `Ollama` (`:11434`): Local inference engine securely hosting `qwen2.5:7b` for generation and embeddings.

---

## Deployment Guide

### Prerequisites
*   [Docker Engine](https://docs.docker.com/get-docker/) & Docker Compose.
*   **Memory:** Minimum 16 GB RAM (32 GB highly recommended for optimal local LLM performance).
*   **Compute:** NVIDIA GPU configured with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (Strongly recommended for GPU-accelerated Ollama inference).

### 1. Initialize Containers

Clone the repository and ignite the Docker environment:
```bash
git clone https://github.com/disorki/High-Precision-RAG-Chunking-Engine/tree/version-2.0
cd high-precision-rag
docker-compose up --build -d
```

### 2. Provision the LLM (Ollama)

Wait for initialization, then pull the target model into the local Ollama instance:
```bash
docker exec -it rag-ollama ollama pull qwen2.5:7b
```
*(Note: You may pull alternative embedding models like `mxbai-embed-large` and update the backend configuration accordingly).*

### 3. Configure the Flowise Agent

1. Access the Flowise dashboard at `http://localhost:3001` (Credentials: `admin` / `admin123`).
2. Navigate to **Chatflows** and click **Add New**.
3. Import the pre-configured cognitive architecture: select **Load Chatflow** and upload `flowise_chatflow.json` (located in the project root).
4. Within the Chatflow settings, generate and copy your unique `API_KEY` and `Chatflow ID`.
5. Inject these credentials into your `docker-compose.yml` under the `frontend` environment variables:
   ```yaml
   - NEXT_PUBLIC_FLOWISE_CHATFLOW_ID=your_chatflow_id
   - FLOWISE_API_KEY=your_api_key
   ```
6. Apply the configuration by restarting the frontend service: `docker restart rag-frontend`

### 4. Access the Platform
Navigate to **[http://localhost:3000](http://localhost:3000)** to access the operational dashboard.
*   **Overview Tab:** Ingest documents via local drag-and-drop or bind your Yandex.Disk for automated cloud retrieval.
*   **Document Analysis Tabs:** Initiate deep querying and analysis with the AI Agent in the "Document" or "All documents" workspaces.

---

## Local Development Setup

For granular debugging or contributing to the codebase without Docker encapsulation:

**Backend Service:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend Client:**
```bash
cd frontend
npm install
npm run dev
```

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.
