"""Pharmacy features: refills, adherence (used by Walgreens & CVS)."""
from __future__ import annotations

from ..fhir.pharmacy import enrich_medication

_CHRONIC_HINTS = ("metformin", "lisinopril", "atorvastatin", "simvastatin", "rosuvastatin",
                  "metoprolol", "amlodipine", "losartan", "levothyroxine", "hydrochlorothiazide",
                  "insulin", "clopidogrel", "warfarin", "omeprazole", "gabapentin")


def _active_meds(patient: dict) -> list[dict]:
    return [enrich_medication(patient["_id"], m) for m in patient.get("medications", [])
            if m.get("status") == "active"]


def refill_insights(patient: dict) -> dict:
    meds = _active_meds(patient)
    refills = [{
        "medication": m["display"], "rxnorm": m["rxnorm"], "status": m["status"],
        "nextRefillDue": m["nextRefillDue"], "daysUntilRefill": m.get("daysUntilRefill"),
        "refillsRemaining": m["refillsRemaining"], "lastFillDate": m["lastFillDate"],
    } for m in meds]
    refills.sort(key=lambda r: (r["daysUntilRefill"] if r["daysUntilRefill"] is not None else 9999))
    return {
        "patientId": patient["_id"],
        "dueSoon": [r for r in refills if r["status"] == "due_soon"],
        "overdue": [r for r in refills if r["status"] == "overdue"],
        "refills": refills,
    }


def adherence(patient: dict) -> dict:
    meds = _active_meds(patient)
    if not meds:
        return {"patientId": patient["_id"], "adherenceScore": None,
                "medSyncCandidates": [], "gaps": [], "note": "No active medications."}
    on_time = sum(1 for m in meds if m["status"] != "overdue")
    score = round(on_time / len(meds), 2)
    gaps = [{"medication": m["display"], "daysLate": -(m["daysUntilRefill"] or 0)}
            for m in meds if m["status"] == "overdue"]
    med_sync = [m["display"] for m in meds
                if any(h in (m["display"] or "").lower() for h in _CHRONIC_HINTS)]
    return {
        "patientId": patient["_id"],
        "adherenceScore": score,
        "medSyncCandidates": med_sync,
        "gaps": gaps,
    }
