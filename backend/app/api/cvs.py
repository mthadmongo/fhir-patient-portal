"""CVS Pharmacy specialized endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import repo
from ..domain import interactions, pharmacy
from ..tenants.deps import require_tenant

router = APIRouter(prefix="/api/cvs", tags=["cvs"],
                   dependencies=[Depends(require_tenant("cvs"))])

_CLINIC_CLASSES = {"AMB", "outpatient"}


@router.get("/patients/{patient_id}/adherence")
def adherence(patient_id: str) -> dict:
    return pharmacy.adherence(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/clinic-visits")
def clinic_visits(patient_id: str) -> dict:
    p = repo.get_patient(patient_id)
    visits = [e for e in p.get("encounters", []) if (e.get("class") or "") in _CLINIC_CLASSES]
    return {"patientId": patient_id, "visits": visits[:15]}


@router.get("/patients/{patient_id}/drug-interactions")
def drug_interactions(patient_id: str) -> dict:
    p = repo.get_patient(patient_id)
    return {"patientId": patient_id, "interactions": interactions.check_interactions(p.get("medications", []))}
