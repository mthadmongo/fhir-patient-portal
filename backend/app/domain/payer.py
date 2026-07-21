"""Payer features (Aetna): care gaps, risk stratification, coverage check."""
from __future__ import annotations

from .labs import _flag  # reuse threshold logic


def _latest(patient: dict, loinc: str) -> dict | None:
    for o in patient.get("observations", []):  # sorted desc by date
        if o.get("loinc") == loinc and o.get("value") is not None:
            return o
    return None


def _active_conditions_text(patient: dict) -> str:
    return " ".join((c.get("display") or "").lower() for c in patient.get("conditions", [])
                    if c.get("clinicalStatus") == "active" and c.get("category") == "clinical")


def care_gaps(patient: dict) -> dict:
    conds = _active_conditions_text(patient)
    gaps: list[dict] = []

    if "diabet" in conds:
        a1c = _latest(patient, "4548-4")
        if a1c is None:
            gaps.append({"measure": "HbA1c Testing", "status": "open",
                         "detail": "Diabetic patient with no HbA1c on record."})
        elif a1c["value"] > 8:
            gaps.append({"measure": "HbA1c Control (<8%)", "status": "open",
                         "detail": f"Latest A1c {a1c['value']}% on {a1c['effectiveDate']}."})
        else:
            gaps.append({"measure": "HbA1c Control (<8%)", "status": "met",
                         "detail": f"Latest A1c {a1c['value']}%."})

    if "hypertension" in conds:
        sbp = _latest(patient, "8480-6")
        if sbp and sbp["value"] > 140:
            gaps.append({"measure": "Blood Pressure Control (<140)", "status": "open",
                         "detail": f"Latest systolic {sbp['value']} mmHg on {sbp['effectiveDate']}."})
        elif sbp:
            gaps.append({"measure": "Blood Pressure Control (<140)", "status": "met",
                         "detail": f"Latest systolic {sbp['value']} mmHg."})

    chol = _latest(patient, "2093-3")
    if chol and chol["value"] > 240:
        gaps.append({"measure": "Cholesterol Management", "status": "open",
                     "detail": f"Total cholesterol {chol['value']} mg/dL (>240)."})

    return {"patientId": patient["_id"], "careGaps": gaps,
            "openCount": sum(1 for g in gaps if g["status"] == "open")}


_RISK_WEIGHTS = [
    (["heart failure", "congestive"], 4, "Heart failure"),
    (["diabet"], 3, "Diabetes"),
    (["ischemic heart", "coronary", "myocardial"], 3, "Coronary/ischemic heart disease"),
    (["chronic kidney", "renal failure"], 3, "Chronic kidney disease"),
    (["stroke", "cerebrovascular"], 3, "Cerebrovascular disease"),
    (["copd", "emphysema", "chronic obstructive"], 2, "COPD"),
    (["cancer", "malignant", "neoplasm"], 2, "Cancer"),
    (["hypertension"], 1, "Hypertension"),
    (["obesity"], 1, "Obesity"),
]


def risk_score(patient: dict) -> dict:
    conds = _active_conditions_text(patient)
    score, contributors = 0, []
    for keywords, weight, label in _RISK_WEIGHTS:
        if any(k in conds for k in keywords):
            score += weight
            contributors.append({"factor": label, "weight": weight})
    age = patient.get("age") or 0
    if age >= 75:
        score += 2
        contributors.append({"factor": "Age 75+", "weight": 2})
    elif age >= 65:
        score += 1
        contributors.append({"factor": "Age 65-74", "weight": 1})
    tier = "high" if score >= 7 else ("medium" if score >= 4 else "low")
    return {"patientId": patient["_id"], "riskScore": score, "riskTier": tier,
            "contributors": contributors}


# Simple formulary: keyword -> coverage.
_FORMULARY = [
    (["metformin", "lisinopril", "amlodipine", "hydrochlorothiazide", "atorvastatin",
      "simvastatin", "losartan", "levothyroxine", "omeprazole", "metoprolol", "aspirin"],
     {"tier": 1, "priorAuth": False, "copay": "$5"}),
    (["insulin", "rosuvastatin", "clopidogrel", "gabapentin", "sertraline", "montelukast"],
     {"tier": 2, "priorAuth": False, "copay": "$25"}),
    (["tegretol", "eliquis", "jardiance", "ozempic", "humira", "prasugrel", "brand"],
     {"tier": 3, "priorAuth": True, "copay": "$60"}),
]


def coverage_check(drug: str) -> dict:
    d = (drug or "").lower()
    for keywords, coverage in _FORMULARY:
        if any(k in d for k in keywords):
            return {"drug": drug, "covered": True, **coverage}
    return {"drug": drug, "covered": True, "tier": 3, "priorAuth": True, "copay": "$60",
            "note": "Non-preferred / not on preferred formulary; prior authorization likely."}
