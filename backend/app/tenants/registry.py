"""Tenant registry + feature catalog.

All tenants share the same dataset; they differ by which features/APIs are exposed.
The frontend renders panels from `/api/me` using each tenant's feature list.
"""
from __future__ import annotations

# Features every tenant gets.
SHARED_FEATURES = [
    {"id": "patient-search", "label": "Patient Search", "method": "GET", "path": "/api/patients",
     "desc": "Hybrid full-text + semantic search across patients."},
    {"id": "patient-summary", "label": "Patient Summary", "method": "GET", "path": "/api/patients/{id}",
     "desc": "Denormalized patient record."},
    {"id": "conditions", "label": "Conditions", "method": "GET", "path": "/api/patients/{id}/conditions",
     "desc": "Patient conditions."},
    {"id": "medications", "label": "Medications", "method": "GET", "path": "/api/patients/{id}/medications",
     "desc": "Patient medications."},
    {"id": "observations", "label": "Labs & Vitals", "method": "GET", "path": "/api/patients/{id}/observations",
     "desc": "Patient labs and vitals."},
    {"id": "chat", "label": "AI Chat", "method": "POST", "path": "/api/chat",
     "desc": "RAG chatbot grounded in patient data (gpt-5.5)."},
]


def _f(fid, label, method, path, desc):
    return {"id": fid, "label": label, "method": method, "path": path, "desc": desc}


TENANTS: dict[str, dict] = {
    "walgreens": {
        "id": "walgreens", "name": "Walgreens", "type": "Pharmacy",
        "theme": {"primary": "#e11837", "accent": "#0089cf"},
        "tagline": "Pharmacy & immunization services",
        "specialized": [
            _f("refill-insights", "Refill Insights", "GET",
               "/api/walgreens/patients/{id}/refill-insights",
               "Medications due or overdue for refill."),
            _f("immunization-eligibility", "Immunization Eligibility", "GET",
               "/api/walgreens/patients/{id}/immunization-eligibility",
               "Recommended vaccines by age & history."),
            _f("drug-interactions", "Drug Interactions", "GET",
               "/api/walgreens/patients/{id}/drug-interactions",
               "Interaction check across active medications."),
        ],
    },
    "cvs": {
        "id": "cvs", "name": "CVS Pharmacy", "type": "Pharmacy",
        "theme": {"primary": "#cc0000", "accent": "#c8102e"},
        "tagline": "Pharmacy, adherence & retail clinics",
        "specialized": [
            _f("medication-adherence", "Medication Adherence", "GET",
               "/api/cvs/patients/{id}/adherence",
               "Adherence score & MedSync candidates."),
            _f("clinic-visits", "Retail Clinic Visits", "GET",
               "/api/cvs/patients/{id}/clinic-visits",
               "Recent outpatient/retail-clinic visit summaries."),
            _f("drug-interactions", "Drug Interactions", "GET",
               "/api/cvs/patients/{id}/drug-interactions",
               "Interaction check across active medications."),
        ],
    },
    "aetna": {
        "id": "aetna", "name": "Aetna", "type": "Payer",
        "theme": {"primary": "#7d3f98", "accent": "#5a2d82"},
        "tagline": "Care gaps, risk & coverage",
        "specialized": [
            _f("care-gaps", "Care Gaps", "GET",
               "/api/aetna/patients/{id}/care-gaps",
               "HEDIS-style care-gap detection."),
            _f("risk-stratification", "Risk Stratification", "GET",
               "/api/aetna/patients/{id}/risk-score",
               "Risk score from conditions & labs."),
            _f("coverage-check", "Formulary / Coverage", "GET",
               "/api/aetna/patients/{id}/coverage-check",
               "Formulary tier & prior-auth check for a drug."),
        ],
    },
    "quest": {
        "id": "quest", "name": "Quest Diagnostics", "type": "Lab",
        "theme": {"primary": "#00857c", "accent": "#006a63"},
        "tagline": "Lab results, trends & diagnostics",
        "specialized": [
            _f("lab-trends", "Lab Trends", "GET",
               "/api/quest/patients/{id}/lab-trends",
               "Time-series trend for a lab (by LOINC)."),
            _f("abnormal-flags", "Abnormal Flags", "GET",
               "/api/quest/patients/{id}/abnormal-flags",
               "Panel of abnormal lab results."),
            _f("test-recommendations", "Test Recommendations", "GET",
               "/api/quest/patients/{id}/test-recommendations",
               "Suggested follow-up tests from conditions & results."),
        ],
    },
}


def list_tenants() -> list[dict]:
    return [
        {"id": t["id"], "name": t["name"], "type": t["type"],
         "theme": t["theme"], "tagline": t["tagline"]}
        for t in TENANTS.values()
    ]


def get_tenant(tenant_id: str) -> dict | None:
    return TENANTS.get(tenant_id)


def tenant_features(tenant_id: str) -> dict:
    t = TENANTS[tenant_id]
    return {
        "id": t["id"], "name": t["name"], "type": t["type"], "theme": t["theme"],
        "tagline": t["tagline"], "shared": SHARED_FEATURES, "specialized": t["specialized"],
    }
