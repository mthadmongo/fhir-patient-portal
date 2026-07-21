# Multi-Tenant FHIR Patient-Portal Chatbot — Technical Spec

> Status: **Planning / spec only. No application code is built yet.**
> Owner: demo engineering
> Last updated: 2026-07-21

---

## 1. Purpose & Narrative

A multi-tenant, RAG-powered web chatbot that lets different healthcare organizations
("tenants") log in and retrieve information about patients from a shared patient portal.

The demo is built to prove two points:

1. **You own your FHIR data.** Patient data lands in **MongoDB Atlas** in its original
   **FHIR R4** format (the source of truth). Because MongoDB stores the raw FHIR and a
   denormalized projection side-by-side, you can extend APIs freely and are **not locked
   into a managed FHIR store** (e.g., Google Cloud Healthcare / FHIR store).
2. **One platform, many tenant-specific products.** The same underlying dataset powers
   **four tenants** that each expose **different features/APIs** on top of the shared data.
   Logging in as Walgreens vs. Aetna surfaces a different set of endpoints, chat tools, and
   UI panels — demonstrating that you can build per-tenant products from data you own.

A secondary highlight is **Atlas Stream Processing (ASP)**: raw FHIR inserted into
`fhir_raw` is transformed into a queryable, denormalized shape **in real time**, which then
feeds **Atlas Full-Text Search** and **Atlas Vector Search**.

---

## 2. Tenants & Differentiation Model

All four tenants share the **same dataset**. Differentiation is by **feature/API**, not by
data isolation. Every tenant gets the shared base APIs; each also exposes 2–3 specialized
APIs (which also become tools the chatbot can call for that tenant).

| Tenant | Type | Specialized angle |
|--------|------|-------------------|
| **Walgreens** | Pharmacy | Refills, immunizations, drug interactions |
| **CVS Pharmacy** | Pharmacy | Adherence/MedSync, retail-clinic visits, drug interactions |
| **Aetna** | Payer / Insurer | Care gaps, risk stratification, formulary/coverage |
| **Quest** | Lab / Diagnostics | Lab trends, abnormal-flag panels, test recommendations |

Auth is intentionally trivial: a **click-to-login** tile per tenant on the landing screen.
Selecting a tenant sets the active tenant context (session) which drives feature gating.

---

## 3. Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11+ | Backend + ingestion/ETL |
| API framework | **FastAPI** | Async, auto OpenAPI docs (reinforces "extend APIs easily") |
| Database | **MongoDB Atlas 8.0** | Source of truth + queryable projection |
| Real-time transform | **Atlas Stream Processing** (SPI `fhir-asp`, tier **SP10**) | FHIR → denormalized, real time |
| Embeddings | **VoyageAI `voyage-4`** | App-side embedding step (approved fallback) |
| LLM | **gpt-5.5 via Grove** | `POST /grove-foundry-prod/openai/v1/responses` |
| Search | **Atlas Search + Atlas Vector Search**, **Hybrid via `$rankFusion`** | Cluster is 8.0 (rankFusion ✓) |
| Frontend | **React (Vite)** | Chat UI, click-to-login, load-batch control |
| Synthetic data | **Synthea** (FHIR R4 bundles) | Java is available in the environment |

### 3.1 Environment / Secrets (already available to the Cloud Agent)

| Secret env var | Purpose |
|----------------|---------|
| `MongoDB_URI_ALL` | Atlas cluster connection string (source of truth cluster) |
| `VoyageAI_API_ALL` | VoyageAI API key (embeddings) |
| `GROVE_LLM_KEY_ALL` | Grove gateway key for gpt-5.5 |

**Grove call shape (gpt-5.5):**

```bash
curl -X POST "https://grove-gateway-prod.azure-api.net/grove-foundry-prod/openai/v1/responses" \
  -H "Content-Type: application/json" \
  -H "api-key: $GROVE_LLM_KEY_ALL" \
  -d '{ "model": "gpt-5.5", "input": "Hello!" }'
```

### 3.2 Atlas Stream Processing coordinates (provisioned by user in Atlas UI)

- **SPI name:** `fhir-asp`
- **Tier:** `SP10`
- **Region:** `virginia-usa` (AWS us-east-1)
- **Cluster connection (registry):** `fhirCluster`
- **SPI connection string:**
  `mongodb://<db_username>:<db_password>@atlas-stream-6a5fc7966d7a84f20587fa00-o2ium.virginia-usa.a.query.mongodb.net/?ssl=true&authSource=admin`
- **Auth:** same DB user as `MongoDB_URI_ALL`.
- Credentials are read from env at deploy time and **never committed**.

---

## 4. Architecture

```
   ┌───────────────────────── React UI (Vite) ─────────────────────────┐
   │  Tenant login tiles │ Chat │ "Load 10 patients" │ Patient panels   │
   └───────────────┬───────────────────────────────┬───────────────────┘
                   │ REST (tenant-scoped)           │
                   ▼                                 ▼
        ┌────────────────────── FastAPI backend ───────────────────────┐
        │  Auth/tenant middleware → Feature registry → Routers          │
        │  Shared routers  +  per-tenant routers (walgreens/cvs/…)      │
        │  RAG service (hybrid search → gpt-5.5)  │  Ingest service      │
        └───────┬─────────────────────┬───────────────────┬────────────┘
                │ VoyageAI embed       │ Grove gpt-5.5      │ insert raw FHIR
                ▼                      ▼                    ▼
        VoyageAI voyage-4        Grove gateway        MongoDB: fhir_raw
                                                             │
                                            Atlas Stream Processor (SP10)
                                   change stream(fhir_raw) → denormalize → $merge
                                                             ▼
                                                    MongoDB: patients
                                          (+ app-side voyage-4 embedding field)
                                                             │
                                        Atlas Search idx  +  Vector Search idx
```

**Ingestion / real-time flow (the "Load Batch" demo):**

1. User clicks **Load 10 patients** → backend inserts 10 raw FHIR bundles into `fhir_raw`.
2. The **Stream Processor** (change stream on `fhir_raw`) denormalizes each patient in real
   time and `$merge`s into `patients`.
3. An **app-side embedding step** picks up the new/updated `patients` docs, computes the
   `voyage-4` embedding of the patient `summaryText`, and writes it back to the doc.
4. **Atlas Search + Vector Search** indexes make the new patients immediately searchable and
   chat-answerable. Running the batch again shows more patients streaming through.

---

## 5. Data Model (MongoDB, db: `patient_portal`)

| Collection | Contents | Written by |
|------------|----------|-----------|
| `fhir_raw` | Raw FHIR R4 resources/bundles, verbatim (source of truth) | Ingest service (Load Batch) |
| `patients` | Denormalized, queryable per-patient doc + `embedding` | ASP (`$merge`) + app-side embed |
| `ingest_state` | Which Synthea patients have been loaded (batch cursor) | Ingest service |
| `dlq_fhir` | Dead-letter for ASP transform errors | ASP DLQ |

Indexes:
- **Atlas Search** (`patients_text`): full-text over name, conditions, medications, labs, `summaryText`.
- **Atlas Vector Search** (`patients_vector`): `embedding` (voyage-4), cosine similarity.
- Standard btree on `patients._id` / identifiers for direct lookups.

> Vector dimension will be set to the `voyage-4` output size (confirmed against the VoyageAI
> API at build time; index `numDimensions` will match exactly).

---

## 6. FHIR Approach

- **Version: FHIR R4 (4.0.1)** — the most widely adopted version and Synthea's native output.
- **Generator: Synthea** — produces realistic synthetic patients (no real PHI; HIPAA out of
  scope for the demo). We generate a pool of ~100 patients and load **10 per batch**,
  repeatable, so the batching + ASP value is visible.
- **Resource types used:** `Patient`, `Condition`, `MedicationRequest`, `Observation`
  (labs/vitals), `AllergyIntolerance`, `Immunization`, `Encounter`. (Others Synthea emits,
  e.g. `Procedure`, `CarePlan`, are stored in `fhir_raw` but not all surfaced.)

### 6.1 Sample raw FHIR patient (abridged Synthea-style, stored in `fhir_raw`)

Each loaded patient is a FHIR `Bundle` of resources. Below are representative entries.

```json
{
  "resourceType": "Patient",
  "id": "3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10",
  "meta": { "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"] },
  "identifier": [
    { "system": "https://github.com/synthetichealth/synthea", "value": "3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10" },
    { "type": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR" }] },
      "system": "http://hospital.smarthealthit.org", "value": "MRN-00482913" }
  ],
  "name": [{ "use": "official", "family": "Hartmann", "given": ["George", "Milton"] }],
  "gender": "male",
  "birthDate": "1957-03-14",
  "address": [{ "line": ["482 Cormier Trail"], "city": "Springfield", "state": "MA", "postalCode": "01103", "country": "US" }],
  "telecom": [{ "system": "phone", "value": "555-427-8831", "use": "home" }],
  "communication": [{ "language": { "coding": [{ "system": "urn:ietf:bcp:47", "code": "en-US" }] } }]
}
```

```json
{
  "resourceType": "Condition",
  "id": "c-91a2",
  "clinicalStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active" }] },
  "verificationStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed" }] },
  "code": { "coding": [{ "system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 diabetes mellitus" }] },
  "subject": { "reference": "Patient/3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10" },
  "onsetDateTime": "2016-08-02T00:00:00Z"
}
```

```json
{
  "resourceType": "MedicationRequest",
  "id": "mr-7742",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": { "coding": [{ "system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "metFORMIN hydrochloride 500 MG Oral Tablet" }] },
  "subject": { "reference": "Patient/3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10" },
  "authoredOn": "2023-01-11T09:20:00Z",
  "dosageInstruction": [{ "text": "500 mg twice daily", "timing": { "repeat": { "frequency": 2, "period": 1, "periodUnit": "d" } } }],
  "dispenseRequest": { "numberOfRepeatsAllowed": 3, "expectedSupplyDuration": { "value": 30, "unit": "days" } }
}
```

```json
{
  "resourceType": "Observation",
  "id": "o-5521",
  "status": "final",
  "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory" }] }],
  "code": { "coding": [{ "system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood" }] },
  "subject": { "reference": "Patient/3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10" },
  "effectiveDateTime": "2024-11-03T08:15:00Z",
  "valueQuantity": { "value": 8.1, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" },
  "interpretation": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "H", "display": "High" }] }],
  "referenceRange": [{ "high": { "value": 5.7, "unit": "%" } }]
}
```

### 6.2 Denormalized patient document (target `patients` shape)

Produced by the Stream Processor (`$merge`), then enriched app-side with `embedding`.
This is the single, queryable per-patient doc that powers search, chat, and every tenant API.

```json
{
  "_id": "3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10",
  "fhirId": "3f2b7c9a-1e44-4a6c-9b2d-7c1f9a2e5d10",
  "source": "fhir_raw",
  "identifiers": { "mrn": "MRN-00482913" },
  "name": { "full": "George Milton Hartmann", "given": "George Milton", "family": "Hartmann" },
  "gender": "male",
  "birthDate": "1957-03-14",
  "age": 69,
  "address": { "city": "Springfield", "state": "MA", "postalCode": "01103" },
  "conditions": [
    { "code": "44054006", "system": "snomed", "display": "Type 2 diabetes mellitus", "clinicalStatus": "active", "onsetDate": "2016-08-02" },
    { "code": "38341003", "system": "snomed", "display": "Essential hypertension", "clinicalStatus": "active", "onsetDate": "2014-05-20" }
  ],
  "medications": [
    { "rxnorm": "860975", "display": "Metformin 500 mg Oral Tablet", "status": "active",
      "authoredOn": "2023-01-11", "dosageText": "500 mg twice daily",
      "daysSupply": 30, "refillsRemaining": 3, "lastFillDate": "2026-06-24", "nextRefillDue": "2026-07-24" },
    { "rxnorm": "197361", "display": "Lisinopril 10 mg Oral Tablet", "status": "active",
      "authoredOn": "2022-09-02", "dosageText": "10 mg once daily",
      "daysSupply": 30, "refillsRemaining": 1, "lastFillDate": "2026-06-30", "nextRefillDue": "2026-07-30" }
  ],
  "observations": [
    { "loinc": "4548-4", "display": "Hemoglobin A1c", "value": 8.1, "unit": "%", "effectiveDate": "2024-11-03", "interpretation": "H" },
    { "loinc": "2339-0", "display": "Glucose", "value": 154, "unit": "mg/dL", "effectiveDate": "2024-11-03", "interpretation": "H" },
    { "loinc": "8480-6", "display": "Systolic blood pressure", "value": 138, "unit": "mmHg", "effectiveDate": "2024-11-03", "interpretation": "N" }
  ],
  "allergies": [
    { "substance": "Penicillin V", "reaction": "Hives", "severity": "moderate" }
  ],
  "immunizations": [
    { "vaccine": "Influenza, seasonal", "date": "2025-10-05" },
    { "vaccine": "COVID-19", "date": "2024-09-18" }
  ],
  "encounters": [
    { "type": "General examination", "class": "ambulatory", "start": "2024-11-03", "provider": "Springfield Primary Care" }
  ],
  "summaryText": "George Milton Hartmann is a 69-year-old male with active Type 2 diabetes mellitus (A1c 8.1% High, 2024-11-03) and essential hypertension. Active medications: Metformin 500 mg twice daily, Lisinopril 10 mg daily. Allergy: Penicillin (hives). Recent flu and COVID-19 vaccinations. Last seen 2024-11-03 for a general examination.",
  "embedding": [0.0123, -0.0456, 0.0789, "…voyage-4 vector…"],
  "lastUpdated": "2026-07-21T19:30:00Z",
  "_streamMeta": { "processedBy": "fhir-denormalize", "sourceTs": "2026-07-21T19:29:58Z" }
}
```

**`summaryText` is the embedded field.** It is a compact natural-language rollup of the
patient's clinically relevant facts — good for both full-text search and semantic retrieval.

---

## 7. Stream Processor Design

Deployed by the agent via `mongosh` connected to SPI `fhir-asp` (`sp.createStreamProcessor`),
then started. Denormalization only (embeddings are app-side).

Pipeline (conceptual):

```js
// source: change stream on raw FHIR
{ $source: { connectionName: "fhirCluster", db: "patient_portal", coll: "fhir_raw",
             config: { fullDocument: "updateLookup" } } },

// keep only patient-bundle inserts/updates we care about
{ $match: { operationType: { $in: ["insert", "replace", "update"] } } },

// flatten FHIR bundle → denormalized patient doc (via $addFields / $project / $map)
{ $addFields: { /* extract name, conditions[], medications[], observations[], summaryText, … */ } },
{ $project:  { /* final denormalized shape (see §6.2, minus embedding) */ } },

// sink: upsert into queryable collection
{ $merge: { into: { connectionName: "fhirCluster", db: "patient_portal", coll: "patients" },
            on: "_id", whenMatched: "merge", whenNotMatched: "insert" } }
```

DLQ: `patient_portal.dlq_fhir`. Notes: `$$NOW`/`$$ROOT` are not valid in ASP — event-time
and document fields are used instead. The exact `$addFields`/`$map` transform will mirror the
app-side denormalizer so both paths produce identical docs.

**Fallback:** if the FHIR-flattening transform is too complex to express purely in the ASP
pipeline, ASP will do the coarse transform + `$merge`, and the app-side denormalizer/embedder
will finish enrichment. Net output shape is identical.

---

## 8. Search & RAG

- **Vector Search** (`patients_vector`) over `embedding` (voyage-4, cosine).
- **Atlas Search** (`patients_text`) over name/conditions/medications/labs/`summaryText`.
- **Hybrid retrieval** with **`$rankFusion`** (MongoDB 8.0 ✓) merging the two pipelines.
- **RAG flow:** user question → voyage-4 embed → hybrid retrieve (top-k, tenant context) →
  build grounded context → **gpt-5.5 via Grove `/responses`** → answer with citations back to
  the patient/resource. No reranker (per decision).
- **Tenant-aware chat tools:** each tenant's specialized APIs are registered as callable tools
  so the chatbot can, e.g., answer "which meds are due for refill?" for Walgreens by invoking
  the refill-insights API.

---

## 9. API Catalog

Base path `/api`. All endpoints require an active tenant (set via click-to-login). Responses
are tenant-scoped where relevant. Specialized endpoints are only mounted/enabled for their
tenant (enforced by the feature registry) — a 404/403 is returned if another tenant calls them.

### 9.1 Shared APIs (all tenants)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tenants` | List tenants for the login screen |
| `POST` | `/api/login` | Click-to-login as a tenant; returns session context |
| `GET` | `/api/me` | Current tenant + enabled features |
| `GET` | `/api/patients` | Search patients (`?query=` full-text/hybrid, paginated) |
| `GET` | `/api/patients/{id}` | Denormalized patient summary |
| `GET` | `/api/patients/{id}/conditions` | Patient conditions |
| `GET` | `/api/patients/{id}/medications` | Patient medications |
| `GET` | `/api/patients/{id}/observations` | Patient labs/vitals (`?loinc=` filter) |
| `POST` | `/api/chat` | RAG Q&A (tenant-scoped, cites patients/resources) |
| `POST` | `/api/ingest/load-batch` | Load next 10 Synthea patients into `fhir_raw` |
| `GET` | `/api/ingest/status` | Counts: raw loaded, denormalized, embedded |

Sample — `POST /api/chat`:

```json
// request
{ "message": "Which of my diabetic patients have an A1c above 8?" }
// response
{
  "answer": "2 patients have an A1c above 8%: George Hartmann (8.1%) and …",
  "citations": [{ "patientId": "3f2b7c9a-…", "field": "observations.4548-4", "value": "8.1 %" }]
}
```

Sample — `POST /api/ingest/load-batch`:

```json
// response
{ "loadedPatientIds": ["…10 ids…"], "batchNumber": 3, "totalRawLoaded": 30,
  "note": "Stream Processor will denormalize these into `patients` momentarily." }
```

### 9.2 Walgreens (Pharmacy) — specialized

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/walgreens/patients/{id}/refill-insights` | Meds due/overdue for refill (uses `nextRefillDue`, `refillsRemaining`) |
| `GET` | `/api/walgreens/patients/{id}/immunization-eligibility` | Recommended vaccines by age/history (flu, COVID, shingles, pneumococcal) |
| `GET` | `/api/walgreens/patients/{id}/drug-interactions` | Drug–drug interaction check across active meds |

Sample — refill-insights:

```json
{ "patientId": "3f2b7c9a-…",
  "refills": [
    { "medication": "Metformin 500 mg", "status": "due_soon", "nextRefillDue": "2026-07-24", "refillsRemaining": 3 },
    { "medication": "Lisinopril 10 mg", "status": "overdue", "nextRefillDue": "2026-07-30", "refillsRemaining": 1 }
  ] }
```

### 9.3 CVS Pharmacy — specialized

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cvs/patients/{id}/adherence` | Adherence score + MedSync sync-eligible meds |
| `GET` | `/api/cvs/patients/{id}/clinic-visits` | Retail-clinic (MinuteClinic-style) visit summaries from encounters |
| `GET` | `/api/cvs/patients/{id}/drug-interactions` | Drug–drug interaction check |

Sample — adherence:

```json
{ "patientId": "3f2b7c9a-…", "adherenceScore": 0.82,
  "medSyncCandidates": ["Metformin 500 mg", "Lisinopril 10 mg"],
  "gaps": [{ "medication": "Lisinopril 10 mg", "daysLate": 5 }] }
```

### 9.4 Aetna (Payer) — specialized

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/aetna/patients/{id}/care-gaps` | HEDIS-style care-gap detection (e.g., A1c, diabetic eye exam, BP control) |
| `GET` | `/api/aetna/patients/{id}/risk-score` | Risk stratification from active conditions/labs |
| `GET` | `/api/aetna/patients/{id}/coverage-check` | Formulary/coverage check (`?rxnorm=`), tier + prior-auth flag |

Sample — care-gaps:

```json
{ "patientId": "3f2b7c9a-…",
  "careGaps": [
    { "measure": "HbA1c Control (<8%)", "status": "open", "detail": "Latest A1c 8.1% (2024-11-03)" },
    { "measure": "Diabetic Retinal Eye Exam", "status": "open", "detail": "No eye exam on record in last 12 months" }
  ] }
```

### 9.5 Quest (Lab / Diagnostics) — specialized

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/quest/patients/{id}/lab-trends` | Time-series of a lab (`?loinc=`) with trend direction |
| `GET` | `/api/quest/patients/{id}/abnormal-flags` | Panel of abnormal (H/L) lab results |
| `GET` | `/api/quest/patients/{id}/test-recommendations` | Suggested follow-up tests from conditions/results |

Sample — abnormal-flags:

```json
{ "patientId": "3f2b7c9a-…",
  "abnormal": [
    { "loinc": "4548-4", "display": "Hemoglobin A1c", "value": 8.1, "unit": "%", "flag": "H", "date": "2024-11-03" },
    { "loinc": "2339-0", "display": "Glucose", "value": 154, "unit": "mg/dL", "flag": "H", "date": "2024-11-03" }
  ] }
```

---

## 10. Frontend (React + Vite)

- **Landing / login:** four tenant tiles (Walgreens, CVS, Aetna, Quest) → click to enter.
- **Top bar:** active tenant, "Load 10 patients" button, ingest status (raw / denormalized /
  embedded counts) to visualize the ASP pipeline.
- **Chat panel:** conversational RAG with streamed answers + citation chips linking to patients.
- **Patient view:** denormalized summary + tabs for conditions/meds/labs.
- **Tenant panel:** renders that tenant's specialized features only (e.g., Walgreens shows
  Refill Insights; Aetna shows Care Gaps). Demonstrates per-tenant product differentiation.

---

## 11. Proposed Repository Layout

```
backend/
  app/
    main.py                  # FastAPI app factory, router mounting
    config.py                # env/secret loading, settings
    db/                      # Mongo client (pooled), collections
    auth/                    # click-to-login, tenant middleware/session
    tenants/                 # tenant + feature registry (which APIs per tenant)
    fhir/                    # FHIR models + denormalizer (mirrors ASP transform)
    ingest/                  # Synthea loader, load-batch, ingest state
    embed/                   # voyage-4 embedding step/worker
    search/                  # index defs + hybrid ($rankFusion) query builder
    chat/                    # RAG service (retrieve → gpt-5.5 via Grove)
    api/
      shared.py              # shared base routers
      walgreens.py cvs.py aetna.py quest.py   # specialized routers
  tests/
streaming/
  processors/fhir_denormalize.json   # ASP pipeline definition
  deploy_processor.py                # create/start via mongosh/SPI
scripts/
  gen_synthea.py            # generate ~100 R4 patients
  create_indexes.py         # Atlas Search + Vector Search (via MCP where possible)
data/synthea/               # generated FHIR bundles (git-ignored if large)
frontend/                   # React (Vite) app
.env.example
README.md
docs/SPEC.md                # this document
```

---

## 12. Phased Build Plan

Each phase ends with a committed, verifiable increment. The **app-side path is built first**
so the demo works end-to-end without ASP; the Stream Processor is layered in at Phase 4.

### Phase 0 — Scaffold & config
- Repo structure, `pyproject.toml`/requirements, `.env.example`, README.
- Mongo client (pooled, per connection best-practices), settings from env secrets.
- **Verify:** app boots; `/health` OK; connects to Atlas; lists `patient_portal`.

### Phase 1 — Synthetic data + Load Batch
- `gen_synthea.py` generates ~100 FHIR R4 patient bundles into `data/synthea/`.
- Ingest service + `POST /api/ingest/load-batch` inserts 10 bundles/call into `fhir_raw`;
  `ingest_state` tracks the cursor; `GET /api/ingest/status`.
- **Verify:** repeated calls load 10 more each; raw docs visible in `fhir_raw`.

### Phase 2 — Denormalization (app-side)
- `fhir/denormalizer.py` transforms a raw bundle → denormalized patient doc (§6.2, no vector).
- Wire denormalizer so loaded patients also land in `patients` (temporary app-side path).
- **Verify:** `patients` docs match the target shape; `summaryText` reads well.

### Phase 3 — Embeddings (voyage-4)
- `embed/` computes voyage-4 embedding of `summaryText`; writes `embedding`; confirms dim.
- Background/idempotent step: embeds any `patients` doc missing/stale `embedding`.
- **Verify:** all `patients` have correct-dimension vectors.

### Phase 4 — Stream Processor (real-time)
- Author `streaming/processors/fhir_denormalize.json`; deploy + start on SPI `fhir-asp` via
  `mongosh` (change stream `fhir_raw` → denormalize → `$merge` `patients`), DLQ configured.
- Switch the app-side denormalization to be a fallback; ASP becomes the primary transform.
- **Verify:** Load Batch → patients appear in `patients` via ASP within seconds; embed step
  fills vectors right after.

### Phase 5 — Search indexes + hybrid retrieval
- Create Atlas Search (`patients_text`) + Vector Search (`patients_vector`) indexes (MCP where
  possible, else `scripts/create_indexes.py`).
- `search/` hybrid `$rankFusion` query builder.
- **Verify:** text, vector, and hybrid queries all return sensible ranked patients.

### Phase 6 — RAG chat
- `chat/` retrieve (hybrid) → context → gpt-5.5 via Grove `/responses` → answer + citations.
- `POST /api/chat`, tenant-scoped.
- **Verify:** clinical questions answered from retrieved patients with citations.

### Phase 7 — Multi-tenancy + specialized APIs
- Tenant + feature registry; click-to-login; tenant middleware; mount shared + specialized
  routers per tenant; register specialized APIs as chat tools.
- Implement all endpoints in §9.
- **Verify:** each tenant exposes exactly its API set; cross-tenant calls blocked; chat tools work.

### Phase 8 — React frontend
- Login tiles, chat, Load-Batch + ingest status, patient views, per-tenant panels.
- **Verify:** full click-through demo for each tenant.

### Phase 9 — Polish
- README + demo script (the exact click-path that best tells the story), seed helper, tests,
  ASP start/stop notes (billing), teardown notes.
- **Verify:** fresh clone → documented steps → working demo.

---

## 13. Cost, Risk & Ops Notes

- **ASP billing:** SP10 bills per-second while **started**; no free tier. The processor will
  be stopped when idle; README documents start/stop.
- **In-pipeline embedding avoided:** embeddings are app-side (approved), removing the need for
  a VoyageAI HTTPS connection in ASP and reducing the failure surface.
- **Complex FHIR flattening in ASP:** if too complex for pure pipeline stages, ASP does the
  coarse transform and the app-side denormalizer finishes it (identical output).
- **Vector dimension:** finalized against the live voyage-4 output before index creation.
- **Secrets:** loaded from env (`MongoDB_URI_ALL`, `VoyageAI_API_ALL`, `GROVE_LLM_KEY_ALL`);
  SPI credentials never committed.
- **No real PHI:** all data is Synthea-synthetic; HIPAA out of scope for the demo.

---

## 14. Open Items to Confirm Before Build

1. **DB name** `patient_portal` acceptable (or an existing db to reuse)?
2. **Patient pool size** ~100 (10 per batch) — good, or generate more so many batches can run?
3. **Specialized API set** in §9 — approve as-is, or adjust any endpoints?
4. Green light to **start Phase 0**.
```
