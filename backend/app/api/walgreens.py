"""Walgreens (pharmacy) specialized endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import repo
from ..domain import immunization, interactions, pharmacy
from ..tenants.deps import require_tenant

router = APIRouter(prefix="/api/walgreens", tags=["walgreens"],
                   dependencies=[Depends(require_tenant("walgreens"))])


@router.get("/patients/{patient_id}/refill-insights")
def refill_insights(patient_id: str) -> dict:
    return pharmacy.refill_insights(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/immunization-eligibility")
def immunization_eligibility(patient_id: str) -> dict:
    return immunization.eligibility(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/drug-interactions")
def drug_interactions(patient_id: str) -> dict:
    p = repo.get_patient(patient_id)
    return {"patientId": patient_id, "interactions": interactions.check_interactions(p.get("medications", []))}
