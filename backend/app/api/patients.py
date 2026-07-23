"""Shared patient + chat endpoints (available to every tenant)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .. import repo
from ..chat.service import chat as rag_chat
from ..tenants.deps import current_tenant

router = APIRouter(prefix="/api", tags=["patients"])


@router.get("/patients")
def search(q: str | None = Query(default=None), limit: int = Query(default=20, ge=1, le=100),
           tenant: dict = Depends(current_tenant)) -> dict:
    results = repo.search_patients(q, limit=limit)
    return {"count": len(results), "patients": [
        {"patientId": p["_id"], "name": p["name"]["full"], "age": p.get("age"),
         "gender": p.get("gender"),
         "activeConditions": [c["display"] for c in p.get("conditions", [])
                              if c.get("clinicalStatus") == "active" and c.get("category") == "clinical"][:5],
         "score": round(p.get("score", 0), 4) if "score" in p else None}
        for p in results]}


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str, tenant: dict = Depends(current_tenant)) -> dict:
    return repo.get_patient(patient_id)


@router.get("/patients/{patient_id}/conditions")
def conditions(patient_id: str, tenant: dict = Depends(current_tenant)) -> dict:
    p = repo.get_patient(patient_id)
    return {"patientId": patient_id, "conditions": p.get("conditions", [])}


@router.get("/patients/{patient_id}/medications")
def medications(patient_id: str, tenant: dict = Depends(current_tenant)) -> dict:
    p = repo.get_patient(patient_id)
    return {"patientId": patient_id, "medications": p.get("medications", [])}


@router.get("/patients/{patient_id}/observations")
def observations(patient_id: str, loinc: str | None = Query(default=None),
                 tenant: dict = Depends(current_tenant)) -> dict:
    p = repo.get_patient(patient_id)
    obs = p.get("observations", [])
    if loinc:
        obs = [o for o in obs if o.get("loinc") == loinc]
    return {"patientId": patient_id, "observations": obs}


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(req: ChatRequest, tenant: dict = Depends(current_tenant)) -> dict:
    return rag_chat(req.message, tenant_name=tenant["name"])
