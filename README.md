# RAG Enterprise Assistant

> A production-ready Document Q&A system built with **LangChain**, **FastAPI**, **pgvector**, and **React/TypeScript** — fully Dockerized, with hybrid search, citations, dual LLM providers, and a RAGAS-scored eval harness.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal?logo=fastapi) ![React](https://img.shields.io/badge/React-18-61DAFB?logo=react) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker) ![LangChain](https://img.shields.io/badge/LangChain-0.2-green) [![CI](https://github.com/Prennoy99/rag-enterprise-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Prennoy99/rag-enterprise-assistant/actions/workflows/ci.yml)

---

## Demo

Upload any PDF, DOCX, or TXT file → ask questions → get streaming AI answers grounded in your documents, with citations back to the source chunk.

```
User: What are the main findings of this report?
Assistant: Based on the uploaded document, the main findings are... (Section 3, doc a1b2c3d4)  ▌
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React / TypeScript                      │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Document Panel   │    │   Chat Interface (SSE stream) │  │
│  │  - Drag & drop   │    │   - Real-time token streaming │  │
│  │  - Status polling│    │   - Document filter + sources │  │
│  └────────┬─────────┘    └──────────────┬───────────────┘  │
└───────────┼──────────────────────────────┼──────────────────┘
            │ REST (multipart/form-data)    │ POST /query/stream
            │ + X-API-Key header             │ + X-API-Key header
            ▼                              ▼
┌────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Python 3.11)              │
│                                                            │
│  POST /api/v1/documents/upload                             │
│    └─► MIME-sniff → Save file → DB record → BackgroundTask │
│           └─► IngestionService                             │
│                 ├─ PyPDF / Docx2txt loader                  │
│                 ├─ RecursiveCharacterTextSplitter            │
│                 └─ OpenAI or Gemini embeddings (batch)       │
│                                                            │
│  POST /api/v1/query/stream                                  │
│    └─► Embed query → hybrid search (RRF)                   │
│           └─► LangChain (OpenAI or Gemini, streaming)        │
│                 └─► Server-Sent Events → client + citations  │
└──────────────────────────┬─────────────────────────────────┘
                           │ asyncpg + SQLAlchemy 2.0 (async)
                           ▼
┌────────────────────────────────────────────────────────────┐
│             PostgreSQL 16 + pgvector extension               │
│                                                            │
│  documents              document_chunks                     │
│  ─────────              ──────────────────────────          │
│  id (UUID)              id (UUID)                            │
│  filename               document_id (FK)                     │
│  status                 content (TEXT)                       │
│  chunk_count            chunk_index (INT)                    │
│                         embedding (vector(1536)) ◄─ HNSW,     │
│                         content_tsv (tsvector) ◄─ GIN,        │
│                              cosine similarity ⊕ full-text    │
│                              fused via Reciprocal Rank Fusion │
└────────────────────────────────────────────────────────────┘
```

Schema is version-controlled via **Alembic migrations** (`backend/alembic/`), not `create_all()`.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React 18 + TypeScript + Tailwind CSS | Type-safe, responsive UI |
| API | FastAPI + Pydantic v2 | Async-first, auto OpenAPI docs |
| Orchestration | LangChain | Industry-standard RAG pipeline |
| Vector Store | pgvector (PostgreSQL 16) | Open-source, no extra infra, HNSW index |
| Retrieval | Hybrid search (pgvector + Postgres full-text, RRF fusion) | Catches both semantic and exact-term matches |
| Embeddings / LLM | OpenAI (`text-embedding-3-small` / `gpt-4o-mini`) **or** Gemini (`gemini-embedding-001` / `gemini-3.1-flash-lite`) | Dual-provider — switch with one env var, no code changes |
| Evaluation | RAGAS (faithfulness, answer relevancy, context precision/recall) | Automated, LLM-graded quality checks in `eval/` |
| Auth | API key (`X-API-Key` header) | Simple, stateless per-deployment auth |
| ORM | SQLAlchemy 2.0 async + asyncpg | Full async stack |
| Migrations | Alembic | Reproducible schema, no `create_all()` in prod |
| Deployment | Docker Compose | One-command local setup |
| CI | GitHub Actions | Backend + frontend test suites on every push |

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- An API key for **at least one** provider:
  - OpenAI → [platform.openai.com/api-keys](https://platform.openai.com/api-keys), or
  - Gemini (free tier) → [aistudio.google.com](https://aistudio.google.com/) — note this requires a Google AI Studio API key, **not** a Google AI Pro/Gemini Advanced subscription, which does not grant API access.

### 1. Clone and configure

```bash
git clone https://github.com/Prennoy99/rag-enterprise-assistant.git
cd rag-enterprise-assistant
cp .env.example .env
# Edit .env: set LLM_PROVIDER=openai (default) or gemini, plus the matching API key,
# and set API_KEY to any string you choose — the frontend/eval scripts read it from here too.
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
3. Wait for status → **Ready** (chunking + embedding runs in the background)
4. Ask questions in the chat panel → answers stream in real time with source citations

---

## Project Structure

```
rag-enterprise-assistant/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routers + Pydantic schemas
│   │   │   ├── documents.py       # Upload, list, delete endpoints
│   │   │   └── query.py           # Streaming SSE query endpoint
│   │   ├── core/               # Config, DB engine, session factory, API-key auth
│   │   ├── models/             # SQLAlchemy ORM (Document, DocumentChunk)
│   │   └── services/
│   │       ├── ingestion.py        # Chunk + embed pipeline (OpenAI/Gemini)
│   │       ├── query.py            # Hybrid search (RRF) + LLM stream
│   │       └── gemini_utils.py     # Embedding truncation/normalization for Gemini
│   ├── alembic/                # Schema migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/         # DocumentUploader, DocumentList, ChatInterface
│   │   ├── services/           # Axios API client + SSE stream generator
│   │   └── types/              # TypeScript interfaces
│   └── Dockerfile
├── eval/                       # RAGAS evaluation harness (isolated deps, talks to app over HTTP)
│   ├── sample_docs/            # Synthetic fixture documents
│   ├── qa_dataset.py           # Q&A pairs with ground truth
│   └── run_eval.py
├── docker/
│   └── init.sql                # pgvector extension bootstrap
├── .github/workflows/ci.yml    # Backend + frontend CI
├── docker-compose.yml
└── .env.example
```

---

## Key Implementation Details

### RAG Pipeline
1. **Ingestion**: Documents are MIME-sniffed (not trusted by client-supplied header), loaded via LangChain loaders, split into chunks with `RecursiveCharacterTextSplitter`
2. **Embedding**: All chunks embedded in a batch call via the active provider (OpenAI `text-embedding-3-small` or Gemini `gemini-embedding-001`, both normalized to 1536 dims), stored as `vector` columns in PostgreSQL via pgvector
3. **Retrieval**: Query is embedded, then results are fused from two ranked lists — pgvector cosine similarity (`<=>`, HNSW-indexed) and Postgres full-text search (`tsvector`/GIN) — combined via **Reciprocal Rank Fusion** (`score = Σ 1/(k + rank + 1)`, k=60)
4. **Generation**: Retrieved chunks form the context for the active provider's chat model, streamed back token-by-token via Server-Sent Events, with source chunks returned alongside the answer for citation

### Why hybrid search over pure vector search?
- Vector similarity alone misses exact keyword/term matches (e.g., product codes, names) that don't cluster semantically
- Full-text search alone misses paraphrases and semantic matches
- RRF fusion combines both ranked lists without needing to tune a blending weight

### Why pgvector over Pinecone?
- **No external service** — runs inside the same PostgreSQL instance as the rest of the app's data
- **ACID transactions** — vector and metadata updates are atomic
- **Open source** — no vendor lock-in, preferred in enterprise/regulated environments
- **SQL native** — filter by metadata using standard WHERE clauses, and combine with full-text search directly in one query

### Dual LLM provider support
Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini` in `.env` — both embeddings and chat swap accordingly, with no code changes and no database migration (Gemini's `gemini-embedding-001` is truncated + L2-renormalized from 3072 to 1536 dims in `gemini_utils.py` to match the existing schema). Only the active provider's API key is required.

---

## Evaluation (RAGAS)

`eval/run_eval.py` runs the live app end-to-end against 10 Q&A pairs over two synthetic sample documents, then scores the results with RAGAS:

| Metric | Score |
|--------|-------|
| Faithfulness | 0.675 |
| Answer Relevancy | 0.875 |
| Context Precision | 0.933 |
| Context Recall | 1.000 |

```bash
# with the stack already running (docker-compose up --build)
cd eval
pip install -r requirements.txt
python run_eval.py
```

The eval harness has its own isolated Python dependencies (talks to the app over HTTP only, no backend code import) to avoid version conflicts with `backend/requirements.txt`. It respects `LLM_PROVIDER` and throttles concurrency automatically when scoring against a free-tier Gemini key (which caps at 15 requests/minute).

---

## API Reference

All endpoints under `/api/v1` require an `X-API-Key` header matching the `API_KEY` set in `.env`.

### Upload Document
```http
POST /api/v1/documents/upload
X-API-Key: <your-api-key>
Content-Type: multipart/form-data

file: <PDF|DOCX|TXT>
```

### List Documents
```http
GET /api/v1/documents/
X-API-Key: <your-api-key>
```

### Stream Query (SSE)
```http
POST /api/v1/query/stream
X-API-Key: <your-api-key>
Content-Type: application/json

{
  "question": "What are the main findings?",
  "document_ids": null
}
```
Streams `data: <token>` chunks, one `data: [SOURCES] <json>` event with the retrieved source chunks, and terminates with `data: [DONE]`.

---

## Testing & CI

```bash
# backend
cd backend && pytest

# frontend
cd frontend && npm test
```

GitHub Actions (`.github/workflows/ci.yml`) runs both suites on every push and pull request.

---

## Roadmap

- [ ] JWT authentication + multi-user support
- [ ] Conversation memory / chat history
- [ ] Support for web URLs and YouTube transcripts
- [ ] Kubernetes deployment manifests
- [ ] Production deployment (Render)

---

## License

MIT
