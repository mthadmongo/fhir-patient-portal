"""Aetna (payer) specialized endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repo
from ..domain import payer
from ..tenants.deps import require_tenant

router = APIRouter(prefix="/api/aetna", tags=["aetna"],
                   dependencies=[Depends(require_tenant("aetna"))])


@router.get("/patients/{patient_id}/care-gaps")
def care_gaps(patient_id: str) -> dict:
    return payer.care_gaps(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/risk-score")
def risk_score(patient_id: str) -> dict:
    return payer.risk_score(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/coverage-check")
def coverage_check(patient_id: str, drug: str = Query(..., description="Drug name to check")) -> dict:
    repo.get_patient(patient_id)  # validate patient exists
    return {"patientId": patient_id, **payer.coverage_check(drug)}
