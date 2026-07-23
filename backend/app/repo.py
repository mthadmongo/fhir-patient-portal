"""Patient data access helpers over the `patients` collection."""
from __future__ import annotations

from fastapi import HTTPException

from .db.mongo import PATIENTS, collection
from .search.service import hybrid_search

_HIDE = {"embedding": 0}


def get_patient(patient_id: str) -> dict:
    p = collection(PATIENTS).find_one({"_id": patient_id}, _HIDE)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
    return p


def search_patients(query: str | None, limit: int = 20) -> list[dict]:
    if query:
        return hybrid_search(query, limit=limit)
    # No query -> list patients by name.
    return list(collection(PATIENTS).find({}, _HIDE).sort("name.full", 1).limit(limit))
