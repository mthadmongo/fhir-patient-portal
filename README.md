# Multi-Tenant FHIR Patient-Portal Chatbot

A RAG-powered, multi-tenant web chatbot over patient data stored in **MongoDB Atlas** in
its original **FHIR R4** format. Four tenants (Walgreens, CVS Pharmacy, Aetna, Quest) log in
and get **different features/APIs** over the **same dataset** — demonstrating that when you
own your FHIR data in MongoDB you can extend APIs freely (no managed FHIR-store lock-in), and
build tenant-specific products on one platform.

See [`docs/SPEC.md`](docs/SPEC.md) for the full technical spec and phased plan.

## Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** MongoDB Atlas 8.0 (`fhir_raw` source of truth → denormalized `patients`)
- **Real-time transform:** Atlas Stream Processing (SPI `fhir-asp`, tier SP10)
- **Embeddings:** VoyageAI `voyage-4` via MongoDB's hosted endpoint (`https://ai.mongodb.com/v1/embeddings`, 1024-dim)
- **LLM:** gpt-5.5 via the Grove gateway
- **Search:** Atlas Search + Vector Search, hybrid via `$rankFusion`
- **Frontend:** React (Vite)

## Environment

Set these (injected as Cloud Agent secrets, or via a local `.env` — see `.env.example`):

| Var | Purpose |
|-----|---------|
| `MongoDB_URI_ALL` | Atlas cluster connection string |
| `VoyageAI_API_ALL` | MongoDB-issued Voyage model API key (Bearer) |
| `GROVE_LLM_KEY_ALL` | Grove gateway key for gpt-5.5 |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Generate patient data (source pool)

```bash
python scripts/gen_synthea.py --count 100
```

Bundles land in `data/synthea/output/fhir/` (git-ignored). Then load them 10 at a time via
`POST /api/ingest/load-batch` (see below).

## Run the backend

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000
```

- Health check: `GET http://127.0.0.1:8000/health`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Build phases

Implemented incrementally (see `docs/SPEC.md` §12):

- [x] **Phase 0** — Scaffold, config, Mongo connection, `/health`
- [x] **Phase 1** — Synthea data + Load-Batch ingest (`fhir_raw`)
- [ ] Phase 2 — App-side FHIR denormalization
- [ ] Phase 3 — voyage-4 embeddings
- [ ] Phase 4 — Atlas Stream Processor (real-time)
- [ ] Phase 5 — Search indexes + hybrid retrieval
- [ ] Phase 6 — RAG chat
- [ ] Phase 7 — Multi-tenancy + specialized APIs
- [ ] Phase 8 — React frontend
- [ ] Phase 9 — Polish
