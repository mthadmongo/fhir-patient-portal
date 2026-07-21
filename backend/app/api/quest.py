"""Quest Diagnostics (lab) specialized endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repo
from ..domain import labs
from ..tenants.deps import require_tenant

router = APIRouter(prefix="/api/quest", tags=["quest"],
                   dependencies=[Depends(require_tenant("quest"))])


@router.get("/patients/{patient_id}/lab-trends")
def lab_trends(patient_id: str, loinc: str = Query(default="4548-4", description="LOINC code")) -> dict:
    return labs.lab_trends(repo.get_patient(patient_id), loinc)


@router.get("/patients/{patient_id}/abnormal-flags")
def abnormal_flags(patient_id: str) -> dict:
    return labs.abnormal_flags(repo.get_patient(patient_id))


@router.get("/patients/{patient_id}/test-recommendations")
def test_recommendations(patient_id: str) -> dict:
    return labs.test_recommendations(repo.get_patient(patient_id))
