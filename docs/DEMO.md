# Demo Walkthrough

A ~5-minute script that tells the story: **own your FHIR data in MongoDB, transform it in
real time, and expose different products per tenant.**

## Setup (once)

```bash
# 1. Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Generate synthetic FHIR patients (needs Java)
python scripts/gen_synthea.py --count 100

# 3. Create Atlas Search + Vector Search indexes
python scripts/create_indexes.py

# 4. (Optional) Deploy the Atlas Stream Processor for real-time denormalization
export PATH="$HOME/.npm-global/bin:$PATH"
python streaming/deploy_processor.py deploy      # BILLING starts (SP10)

# 5. Run backend + frontend (two terminals)
#    ASP running -> APP_SIDE_DENORMALIZE=false ; else leave default (true)
APP_SIDE_DENORMALIZE=false uvicorn backend.app.main:app --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## The story (click-path)

1. **Own the FHIR data.** Show `fhir_raw` in Atlas — raw FHIR R4 bundles stored verbatim.
   "MongoDB is the FHIR store; no Google/managed FHIR-store lock-in."

2. **Real-time transform.** In the app top bar, click **Load 10 patients**. Explain that raw
   FHIR was inserted into `fhir_raw`, the **Atlas Stream Processor** denormalized it into the
   queryable `patients` collection in real time, and voyage-4 embeddings were added. Watch the
   **Raw / Patients / Embedded** counters climb. Click it again to stream in more.
   (Show `python streaming/deploy_processor.py status` — inputMessageCount rising, DLQ 0.)

3. **Full-text + vector search.** In the patient list, search "diabetes" or "heart disease" —
   this is hybrid (`$rankFusion`) Atlas Search + Vector Search over the denormalized data.

4. **Grounded AI chat.** Open **AI Chat** and ask *"Which patients have diabetes with poor
   glucose control?"* or *"Who is on statins for heart disease?"* — gpt-5.5 answers from
   retrieved patients with clickable citations.

5. **Different products per tenant.** Click **Switch tenant** and log in as each:
   - **Walgreens** → open a patient → **Refill Insights**, **Immunization Eligibility**,
     **Drug Interactions**.
   - **CVS Pharmacy** → **Medication Adherence**, **Retail Clinic Visits**, **Drug Interactions**.
   - **Aetna** → **Care Gaps**, **Risk Stratification**, **Formulary / Coverage**.
   - **Quest** → **Lab Trends**, **Abnormal Flags**, **Test Recommendations**.

   Same dataset, different APIs and UI per tenant. (Bonus: calling another tenant's API returns
   `403` — features are gated by the tenant feature registry.)

6. **Wrap up.** One MongoDB platform stores FHIR, transforms it in real time, powers
   search + AI, and serves tenant-specific products — all from data you own.

## Cleanup

```bash
python streaming/deploy_processor.py stop   # stop billing (state retained 45 days)
```
