# AI-Powered Document & Multimedia Q&A

Full-stack web app that ingests PDFs, audio, and video files, extracts text (PDF parsing + Whisper ASR for media), embeds chunks into a vector store, and lets users ask questions with semantic retrieval and streaming LLM answers. For media files, citations include timestamps and a **Play** button jumps the embedded player to that exact position.

- **Backend:** Python 3.12 · FastAPI · MongoDB (Motor) · OpenAI (chat/embeddings/Whisper)
- **Frontend:** React 18 · Vite · React Router · plain CSS
- **DevOps:** Docker Compose (mongo + redis + backend + frontend) · GitHub Actions CI · 97% backend test coverage

---

## Features

| # | Capability | Where |
|---|---|---|
| 1 | Upload PDF / audio / video | `POST /api/files` · `components/Uploader.jsx` |
| 2 | PDF text extraction | `services/extraction.py` (pypdf) |
| 3 | Audio/video transcription | `services/llm.py` (OpenAI Whisper) |
| 4 | Chunking + embeddings + vector search | `services/ingestion.py`, `services/vector_store.py` |
| 5 | LLM chatbot (non-streaming) | `POST /api/chat` |
| 6 | LLM chatbot (streaming SSE) | `POST /api/chat/stream` |
| 7 | Auto summary of each file | `GET /api/files/{id}/summary` |
| 8 | Timestamp search for a topic | `POST /api/chat/timestamps` |
| 9 | Play button jumps to citation | `components/ChatPanel.jsx` + `MediaPlayer.jsx` |
| 10 | JWT auth (register / login / me) | `routers/auth.py` |
| 11 | Rate limiting (Redis or in-memory) | `services/rate_limit.py` |
| 12 | Answer caching (Redis or in-memory) | `services/cache.py` |
| 13 | Per-file multi-tenant isolation | `owner_id` scoping |
| 14 | 97% test coverage | `backend/pytest.ini` (`--cov-fail-under=95`) |
| 15 | CI builds + tests + docker images | `.github/workflows/ci.yml` |

> Offline-friendly: if `OPENAI_API_KEY` is unset, the backend falls back to deterministic stub embeddings / answers / transcripts so you can run the full pipeline end-to-end without incurring cost. Set the key in production for real results.

---

## Repository layout

```
panscience-assignment/
├─ backend/                 FastAPI service
│  ├─ app/
│  │  ├─ main.py            app factory + CORS + lifespan
│  │  ├─ config.py          env-driven settings
│  │  ├─ database.py        motor client + index setup
│  │  ├─ deps.py            auth + rate-limit dependencies
│  │  ├─ models.py          pydantic DTOs
│  │  ├─ routers/           auth, files, chat endpoints
│  │  └─ services/          extraction, llm, ingestion, vector_store, cache, rate_limit, security
│  ├─ tests/                pytest suites (97% cov)
│  ├─ requirements.txt
│  ├─ requirements-dev.txt
│  ├─ Dockerfile
│  └─ pytest.ini
├─ frontend/                React SPA (Vite)
│  ├─ src/
│  │  ├─ api.js             fetch/axios client (+ SSE stream parser)
│  │  ├─ context/           AuthContext
│  │  ├─ pages/             AuthPage, WorkspacePage
│  │  └─ components/        Uploader, FileList, FileDetail, ChatPanel, Timestamps, MediaPlayer
│  ├─ Dockerfile
│  ├─ nginx.conf
│  └─ vite.config.js
├─ docker-compose.yml
├─ .github/workflows/ci.yml
├─ .env.example
└─ README.md
```

---

## Quick start

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env           # edit OPENAI_API_KEY and JWT_SECRET
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- MongoDB: `localhost:27017` · Redis: `localhost:6379`

### Option B — Run services locally

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate  # Windows bash: .venv/Scripts/activate
pip install -r requirements-dev.txt
export MONGO_URI=mongodb://localhost:27017             # or mongomock for tests
export JWT_SECRET=dev
export OPENAI_API_KEY=sk-...                           # optional
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxied to backend on :8000
```

---

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Connection string |
| `MONGO_DB`  | `ai_qa` | Database name |
| `JWT_SECRET` | `change-me-in-production` | HS256 signing key |
| `JWT_EXPIRES_MINUTES` | `1440` | Token lifetime |
| `OPENAI_API_KEY` | _(empty → offline stub mode)_ | Required for real LLM/ASR |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | |
| `OPENAI_TRANSCRIBE_MODEL` | `whisper-1` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `REDIS_ENABLED` | `false` | Turn on for prod rate-limit + cache |
| `UPLOAD_DIR` | `./uploads` | Where original files are stored |
| `MAX_UPLOAD_MB` | `200` | Reject larger uploads |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-user / per-IP quota |
| `CORS_ORIGINS` | `*` | Comma-separated |

---

## API reference

All endpoints are JSON unless noted. Authenticated endpoints require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | `{email, password}` → `{access_token}` |
| POST | `/api/auth/login` | `{email, password}` → `{access_token}` |
| GET  | `/api/auth/me` | Current user |

### Files

| Method | Path | Description |
|---|---|---|
| POST   | `/api/files` | `multipart/form-data` with `file=@...`. Returns `FileOut`. Ingestion runs in background. |
| GET    | `/api/files` | List your files |
| GET    | `/api/files/{id}` | One file, includes `status`, `summary`, `duration_seconds`, `error` |
| GET    | `/api/files/{id}/summary` | `{file_id, summary}` |
| GET    | `/api/files/{id}/media` | Raw file bytes (used by `<audio>` / `<video>`) |
| DELETE | `/api/files/{id}` | Remove file + chunks + blob |

### Chat & timestamps

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | `{file_id, question, top_k?}` → `{answer, citations[]}`. Cached for 5 min. |
| POST | `/api/chat/stream` | Same input; returns `text/event-stream` with events `citations`, `token`, `done`. |
| POST | `/api/chat/timestamps` | `{file_id, topic, top_k?}` → `{hits: [{chunk_id, text, start_time, end_time, score}]}`. Only for audio/video. |

### Misc

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{status: "ok", version}` |
| GET | `/docs` | Auto-generated Swagger UI |

---

## Architecture

```
 ┌────────┐  upload   ┌──────────────┐   motor   ┌──────────┐
 │ React  │──────────▶│  FastAPI     │──────────▶│ MongoDB  │
 │  SPA   │◀──── SSE ─│  (routers)   │◀──────────│          │
 └────────┘           └──────┬───────┘           └──────────┘
                             │ services
          ┌──────────────────┼──────────────────────┐
          ▼                  ▼                      ▼
   extraction (pypdf)   llm (OpenAI /          vector_store
   ingestion pipeline   Whisper / stubs)       (cosine in-DB)
          │                  │                      │
          └──── background task queued by FastAPI ──┘
```

**Ingestion pipeline** (`services/ingestion.py`):
1. Detect file kind (PDF / audio / video).
2. Extract text (pypdf) or transcribe via Whisper, capturing `(start,end,text)` segments.
3. Chunk by character budget with sentence-aware splits; for media, chunk along segment boundaries so each chunk carries a `(start_time, end_time)`.
4. Embed chunks with OpenAI embeddings (or deterministic hash-based stub).
5. Persist chunks + embeddings in the `chunks` Mongo collection.
6. Generate a summary of the full text.
7. Flip the file row to `status=ready`.

**Retrieval:** cosine similarity over stored embeddings, top-k chunks → LLM with strict "answer from context only" system prompt. Citations echo chunk text, score, and timestamps so the UI can render Play buttons.

---

## Testing

```bash
cd backend
pytest                     # full suite with coverage gate
pytest tests/test_auth_api.py -q
```

- 81 tests across services and API routes.
- `pytest.ini` enforces `--cov-fail-under=95` (current: **97.6%**).
- MongoDB is mocked with `mongomock-motor`; Redis with `fakeredis`; OpenAI paths exercised via lightweight stub objects.

Sample coverage report:
```
TOTAL   789    19    98%
Required test coverage of 95% reached. Total coverage: 97.59%
```

### Frontend

```bash
cd frontend
npm run build              # static build
npm run dev                # dev server with /api proxy
```

---

## CI/CD

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push/PR:

1. **backend-tests** — installs `requirements-dev.txt`, runs `pytest` with the 95% coverage gate.
2. **frontend-build** — `npm install && npm run build`.
3. **docker-build** — builds both images via `docker/build-push-action` after the first two succeed.

---

## Deployment notes

The Compose stack is deploy-ready for any single-VM target (AWS EC2, GCP GCE, Azure VM, Fly, Render). For managed deploys:

- **Backend**: build `backend/Dockerfile`, set env vars above, mount a volume at `/data/uploads`, expose 8000.
- **Frontend**: build `frontend/Dockerfile` (serves via Nginx on :80); point `/api` traffic at the backend service.
- **MongoDB**: any managed Mongo (Atlas, DocumentDB, CosmosDB Mongo API).
- **Redis (optional)**: Elasticache / Memorystore / Upstash. Set `REDIS_ENABLED=true`.

For production-grade vector search, swap `services/vector_store.py` for MongoDB Atlas Vector Search or FAISS with a persisted index; the call sites already pass an embedding vector and `top_k`.

---

## Security

- Passwords hashed with bcrypt (cost 12, via passlib).
- JWTs signed with HS256; `/api/auth/me` validates on every request.
- Every file query is scoped by `owner_id` — no cross-tenant access.
- Rate limits per-IP on auth endpoints and per-user on chat endpoints (60/min default).
- CORS configurable via `CORS_ORIGINS`.
- File type enforced by extension + content-type; oversized uploads rejected with 413.

---

## License

MIT.
