# RAG Enterprise Assistant

> A production-ready Document Q&A system built with **LangChain**, **FastAPI**, **pgvector**, and **React/TypeScript** — fully Dockerized.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal?logo=fastapi) ![React](https://img.shields.io/badge/React-18-61DAFB?logo=react) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker) ![LangChain](https://img.shields.io/badge/LangChain-0.2-green)

---

## Demo

Upload any PDF, DOCX, or TXT file → ask questions → get streaming AI answers grounded in your documents.

```
User: What are the main findings of this report?
Assistant: Based on the uploaded document, the main findings are...  ▌
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React / TypeScript                      │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Document Panel   │    │   Chat Interface (SSE stream) │  │
│  │  - Drag & drop   │    │   - Real-time token streaming │  │
│  │  - Status polling│    │   - Document filter           │  │
│  └────────┬─────────┘    └──────────────┬───────────────┘  │
└───────────┼──────────────────────────────┼──────────────────┘
            │ REST (multipart/form-data)    │ POST /query/stream
            ▼                              ▼
┌────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Python 3.11)              │
│                                                            │
│  POST /api/v1/documents/upload                             │
│    └─► Save file → Create DB record → BackgroundTask       │
│           └─► IngestionService                             │
│                 ├─ PyPDF / Docx2txt loader                 │
│                 ├─ RecursiveCharacterTextSplitter           │
│                 └─ OpenAI Embeddings (batch)               │
│                                                            │
│  POST /api/v1/query/stream                                 │
│    └─► Embed query → pgvector cosine search               │
│           └─► LangChain (ChatOpenAI streaming)             │
│                 └─► Server-Sent Events → client            │
└──────────────────────────┬─────────────────────────────────┘
                           │ asyncpg + SQLAlchemy 2.0
                           ▼
┌────────────────────────────────────────────────────────────┐
│             PostgreSQL 16 + pgvector extension             │
│                                                            │
│  documents              document_chunks                    │
│  ─────────              ──────────────────────────         │
│  id (UUID)              id (UUID)                          │
│  filename               document_id (FK)                   │
│  status                 content (TEXT)                     │
│  chunk_count            chunk_index (INT)                  │
│                         embedding (vector(1536)) ◄─ cosine │
└────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React 18 + TypeScript + Tailwind CSS | Type-safe, responsive UI |
| API | FastAPI + Pydantic v2 | Async-first, auto OpenAPI docs |
| Orchestration | LangChain | Industry-standard RAG pipeline |
| Vector Store | pgvector (PostgreSQL) | Open-source, no extra infra |
| Embeddings | OpenAI `text-embedding-3-small` | Cost-efficient, 1536 dimensions |
| LLM | OpenAI `gpt-4o-mini` | Fast, affordable, high quality |
| ORM | SQLAlchemy 2.0 async + asyncpg | Full async stack |
| Deployment | Docker Compose | One-command local setup |

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- OpenAI API key → [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### 1. Clone and configure

```bash
git clone https://github.com/SB-new/RAG-enterprise-assistant.git
cd RAG-enterprise-assistant
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

### 2. Start everything

```bash
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

### 3. Use it
1. Open **http://localhost:3000**
2. Upload a PDF, DOCX, or TXT document
3. Wait for status → **Ready** (embedding runs in background)
4. Ask questions in the chat panel → answers stream in real time

---

## Project Structure

```
rag-enterprise-assistant/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers + Pydantic schemas
│   │   │   ├── documents.py   # Upload, list, delete endpoints
│   │   │   └── query.py       # Streaming SSE query endpoint
│   │   ├── core/          # Config, DB engine, session factory
│   │   ├── models/        # SQLAlchemy ORM (Document, DocumentChunk)
│   │   └── services/
│   │       ├── ingestion.py   # Chunk + embed pipeline
│   │       └── query.py       # Vector search + LLM stream
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # DocumentUploader, DocumentList, ChatInterface
│   │   ├── services/      # Axios API client + SSE stream generator
│   │   └── types/         # TypeScript interfaces
│   └── Dockerfile
├── docker/
│   └── init.sql           # pgvector extension bootstrap
├── docker-compose.yml
└── .env.example
```

---

## Key Implementation Details

### RAG Pipeline
1. **Ingestion**: Documents are loaded via LangChain loaders, split into 1000-token chunks with 200-token overlap using `RecursiveCharacterTextSplitter`
2. **Embedding**: All chunks embedded in a single OpenAI batch call (`text-embedding-3-small`, 1536 dims), stored as `vector` columns in PostgreSQL via pgvector
3. **Retrieval**: Query is embedded, then top-5 chunks retrieved using pgvector's native cosine similarity operator (`<=>`)
4. **Generation**: Retrieved chunks form the context for a `gpt-4o-mini` prompt, streamed back token-by-token via Server-Sent Events

### Why pgvector over Pinecone?
- **No external service** — runs inside your existing PostgreSQL instance
- **ACID transactions** — vector and metadata updates are atomic
- **Open source** — no vendor lock-in, preferred in enterprise/regulated environments
- **SQL native** — filter by metadata using standard WHERE clauses

---

## API Reference

### Upload Document
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: <PDF|DOCX|TXT>
```

### List Documents
```http
GET /api/v1/documents/
```

### Stream Query (SSE)
```http
POST /api/v1/query/stream
Content-Type: application/json

{
  "question": "What are the main findings?",
  "document_ids": null
}
```

---

## Roadmap

- [ ] JWT authentication + multi-user support
- [ ] Hybrid search (BM25 + vector re-ranking)
- [ ] Conversation memory / chat history
- [ ] Support for web URLs and YouTube transcripts
- [ ] Kubernetes deployment manifests
- [ ] Evaluation framework (RAGAS)

---

## License

MIT
