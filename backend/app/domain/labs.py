"""Lab-centric features (Quest): trends, abnormal flags, test recommendations."""
from __future__ import annotations

# loinc -> (low, high, label). Used to flag abnormal values when FHIR interpretation is absent.
REF_RANGES = {
    "4548-4": (None, 6.5, "Hemoglobin A1c"),
    "2339-0": (70, 125, "Glucose"),
    "2093-3": (None, 200, "Total cholesterol"),
    "2571-8": (None, 150, "Triglycerides"),
    "38483-4": (0.6, 1.3, "Creatinine"),
    "6299-2": (7, 20, "BUN"),
    "8480-6": (90, 140, "Systolic BP"),
    "8462-4": (60, 90, "Diastolic BP"),
    "39156-5": (18.5, 30, "BMI"),
    "718-7": (12, 17.5, "Hemoglobin"),
    "789-8": (4.2, 5.9, "RBC"),
}


def _flag(loinc: str, value) -> str | None:
    rng = REF_RANGES.get(loinc)
    if not rng or value is None:
        return None
    low, high, _ = rng
    if high is not None and value > high:
        return "H"
    if low is not None and value < low:
        return "L"
    return None


def lab_trends(patient: dict, loinc: str) -> dict:
    obs = [o for o in patient.get("observations", []) if o.get("loinc") == loinc and o.get("value") is not None]
    obs.sort(key=lambda o: o.get("effectiveDate") or "")
    series = [{"date": o["effectiveDate"], "value": o["value"], "unit": o.get("unit"),
               "flag": o.get("interpretation") or _flag(loinc, o.get("value"))} for o in obs]
    trend = None
    if len(series) >= 2:
        delta = series[-1]["value"] - series[0]["value"]
        trend = "increasing" if delta > 0 else ("decreasing" if delta < 0 else "stable")
    label = REF_RANGES.get(loinc, (None, None, None))[2] or (obs[0]["display"] if obs else loinc)
    return {"patientId": patient["_id"], "loinc": loinc, "label": label,
            "count": len(series), "trend": trend, "series": series}


def abnormal_flags(patient: dict) -> dict:
    latest: dict[str, dict] = {}
    for o in patient.get("observations", []):  # already sorted desc by date
        if o["loinc"] not in latest:
            latest[o["loinc"]] = o
    abnormal = []
    for loinc, o in latest.items():
        flag = o.get("interpretation") or _flag(loinc, o.get("value"))
        if flag in ("H", "L", "HH", "LL", "A"):
            abnormal.append({"loinc": loinc, "display": o.get("display"), "value": o.get("value"),
                             "unit": o.get("unit"), "flag": flag, "date": o.get("effectiveDate")})
    return {"patientId": patient["_id"], "abnormal": abnormal}


def test_recommendations(patient: dict) -> dict:
    conds = " ".join((c.get("display") or "").lower() for c in patient.get("conditions", [])
                     if c.get("clinicalStatus") == "active")
    meds = " ".join((m.get("display") or "").lower() for m in patient.get("medications", [])
                    if m.get("status") == "active")
    recs: list[dict] = []

    def add(test, reason):
        recs.append({"test": test, "reason": reason})

    if "diabet" in conds:
        add("Hemoglobin A1c (every 3 months)", "Active diabetes management.")
        add("Lipid panel", "Cardiovascular risk in diabetes.")
        add("Urine microalbumin / eGFR", "Screen for diabetic nephropathy.")
    if "hypertension" in conds:
        add("Basic metabolic panel", "Monitor renal function / electrolytes on antihypertensives.")
    if "statin" in meds or any(s in meds for s in ["atorvastatin", "simvastatin", "rosuvastatin"]):
        add("Liver function tests (ALT/AST)", "Statin therapy monitoring.")
    if "kidney" in conds or "renal" in conds:
        add("eGFR & Creatinine", "Chronic kidney disease monitoring.")
    if not recs:
        add("Annual wellness labs (CBC, CMP, lipid panel)", "Routine preventive screening.")
    return {"patientId": patient["_id"], "recommendations": recs}
