"""Transform a raw FHIR Bundle into a denormalized, queryable patient document.

This is the app-side implementation of the FHIR -> queryable transform. The Atlas
Stream Processor (Phase 4) mirrors this logic so both paths produce the same shape.

Notes on synthetic data:
- Synthea rarely emits `dispenseRequest`, so refill fields (daysSupply, refills
  remaining, last/next fill dates) are synthesized *deterministically* per
  (patientId, rxnorm) so the pharmacy/adherence demos are meaningful and stable.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

_DIGITS = re.compile(r"\d+$")

# Synthea encodes social determinants of health as SNOMED "conditions"
# (employment, education, etc.). We keep them in the data but tag them "social"
# so clinical summaries/views focus on actual medical conditions.
_SDOH_KEYWORDS = (
    "employment", "education", "school", "social contact", "social isolation",
    "housing", "criminal record", "refugee", "immigrant", "unemploy",
    "labor force", "risk activity", "transport", "food ", "victim",
    "violence", "medication review due", "higher education", "primary school",
    "part time", "part-time", "full time", "full-time", "retired",
    "not in labor", "certificate of high school", "sexually active",
    "stress (finding)", "reports of", "received ", "has a criminal",
)


def _condition_category(display: str | None) -> str:
    d = (display or "").lower()
    return "social" if any(k in d for k in _SDOH_KEYWORDS) else "clinical"


def _date10(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value[:10]


def _clean_name(token: str) -> str:
    return _DIGITS.sub("", token or "").strip()


def _coding(concept: dict | None) -> dict:
    """Return the first coding dict from a CodeableConcept, or {}."""
    if not concept:
        return {}
    for c in concept.get("coding", []):
        return c
    return {}


def _system_short(system: str | None) -> str:
    if not system:
        return ""
    s = system.lower()
    if "snomed" in s:
        return "snomed"
    if "loinc" in s:
        return "loinc"
    if "rxnorm" in s:
        return "rxnorm"
    if "cvx" in s:
        return "cvx"
    return system


def _age(birth_date: str | None) -> int | None:
    d = _date10(birth_date)
    if not d:
        return None
    try:
        y, m, day = (int(x) for x in d.split("-"))
        today = date.today()
        return today.year - y - ((today.month, today.day) < (m, day))
    except Exception:
        return None


def _resources_by_type(bundle: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        rt = res.get("resourceType")
        if rt:
            out.setdefault(rt, []).append(res)
    return out


# ----------------------------- section builders -----------------------------

def _patient_fields(patient: dict) -> dict:
    name = (patient.get("name") or [{}])[0]
    given = " ".join(_clean_name(g) for g in name.get("given", []) if g)
    family = _clean_name(name.get("family", ""))
    full = " ".join(x for x in [given, family] if x).strip()

    mrn = None
    for ident in patient.get("identifier", []):
        if _coding(ident.get("type")).get("code") == "MR":
            mrn = ident.get("value")
    addr = (patient.get("address") or [{}])[0]

    return {
        "identifiers": {"mrn": mrn},
        "name": {"full": full, "given": given, "family": family},
        "gender": patient.get("gender"),
        "birthDate": _date10(patient.get("birthDate")),
        "age": _age(patient.get("birthDate")),
        "address": {
            "city": addr.get("city"),
            "state": addr.get("state"),
            "postalCode": addr.get("postalCode"),
        },
    }


def _conditions(items: list[dict]) -> list[dict]:
    by_code: dict[str, dict] = {}
    for c in items:
        code = _coding(c.get("code"))
        key = code.get("code")
        if not key:
            continue
        status = _coding(c.get("clinicalStatus")).get("code")
        onset = _date10(c.get("onsetDateTime")) or _date10(c.get("recordedDate"))
        display = code.get("display") or (c.get("code") or {}).get("text")
        entry = {
            "code": key,
            "system": _system_short(code.get("system")),
            "display": display,
            "clinicalStatus": status,
            "onsetDate": onset,
            "category": _condition_category(display),
        }
        prev = by_code.get(key)
        # keep earliest onset; prefer an active status if seen
        if not prev:
            by_code[key] = entry
        else:
            if (onset or "9999") < (prev.get("onsetDate") or "9999"):
                prev["onsetDate"] = onset
            if status == "active":
                prev["clinicalStatus"] = "active"
    return sorted(by_code.values(), key=lambda x: x.get("onsetDate") or "")


def _medications(items: list[dict]) -> list[dict]:
    by_code: dict[str, dict] = {}
    for m in items:
        concept = m.get("medicationCodeableConcept")
        code = _coding(concept)
        key = code.get("code")
        if not key:
            continue
        authored = _date10(m.get("authoredOn"))
        dosage = ""
        for di in m.get("dosageInstruction", []):
            if di.get("text"):
                dosage = di["text"]
                break
        status = m.get("status")
        entry = {
            "rxnorm": key,
            "display": code.get("display") or (concept or {}).get("text"),
            "status": status,
            "authoredOn": authored,
            "dosageText": dosage,
        }
        prev = by_code.get(key)
        if not prev or (authored or "") > (prev.get("authoredOn") or ""):
            if prev and prev.get("status") == "active":
                entry["status"] = "active"
            by_code[key] = entry
        elif status == "active":
            prev["status"] = "active"

    return sorted(by_code.values(), key=lambda x: x.get("authoredOn") or "", reverse=True)


def _one_observation(code: dict, value_obj: dict, obs: dict, category: str) -> dict | None:
    loinc = code.get("code")
    if not loinc:
        return None
    interp = _coding((obs.get("interpretation") or [{}])[0]).get("code")
    return {
        "loinc": loinc,
        "display": code.get("display") or (obs.get("code") or {}).get("text"),
        "value": value_obj.get("value"),
        "unit": value_obj.get("unit"),
        "effectiveDate": _date10(obs.get("effectiveDateTime")) or _date10(obs.get("issued")),
        "interpretation": interp,
        "category": category,
    }


def _observations(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for o in items:
        cats = {
            cc.get("code")
            for c in o.get("category", [])
            for cc in c.get("coding", [])
        }
        category = "laboratory" if "laboratory" in cats else (
            "vital-signs" if "vital-signs" in cats else None
        )
        if category is None:
            continue  # skip survey/social-history/procedure
        code = _coding(o.get("code"))
        if "valueQuantity" in o:
            rec = _one_observation(code, o["valueQuantity"], o, category)
            if rec:
                out.append(rec)
        elif "component" in o:  # e.g., blood pressure -> systolic/diastolic
            for comp in o.get("component", []):
                ccode = _coding(comp.get("code"))
                if "valueQuantity" in comp:
                    rec = _one_observation(ccode, comp["valueQuantity"], o, category)
                    if rec:
                        out.append(rec)
    out.sort(key=lambda x: x.get("effectiveDate") or "", reverse=True)
    return out


def _allergies(items: list[dict]) -> list[dict]:
    out = []
    for a in items:
        substance = _coding(a.get("code")).get("display") or (a.get("code") or {}).get("text")
        reaction, severity = None, None
        for r in a.get("reaction", []):
            severity = r.get("severity")
            m = (r.get("manifestation") or [{}])[0]
            reaction = _coding(m).get("display") or m.get("text")
            break
        out.append({"substance": substance, "reaction": reaction, "severity": severity})
    return out


def _immunizations(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for i in items:
        vaccine = (i.get("vaccineCode") or {}).get("text") or _coding(i.get("vaccineCode")).get("display")
        d = _date10(i.get("occurrenceDateTime"))
        key = (vaccine, d)
        if key in seen:
            continue
        seen.add(key)
        out.append({"vaccine": vaccine, "date": d})
    return sorted(out, key=lambda x: x.get("date") or "", reverse=True)


def _encounters(items: list[dict]) -> list[dict]:
    out = []
    for e in items:
        etype = (e.get("type") or [{}])[0]
        provider = None
        for p in e.get("participant", []):
            ind = p.get("individual", {})
            if ind.get("display"):
                provider = ind["display"]
                break
        if not provider:
            provider = (e.get("serviceProvider") or {}).get("display")
        out.append({
            "type": _coding(etype).get("display") or etype.get("text"),
            "class": (e.get("class") or {}).get("code"),
            "start": _date10((e.get("period") or {}).get("start")),
            "provider": provider,
        })
    return sorted(out, key=lambda x: x.get("start") or "", reverse=True)


# --------------------------------- summary ----------------------------------

_KEY_LABS = {
    "4548-4": "A1c", "2339-0": "Glucose", "2093-3": "Total cholesterol",
    "2571-8": "Triglycerides", "6299-2": "BUN", "38483-4": "Creatinine",
    "8480-6": "Systolic BP", "8462-4": "Diastolic BP", "39156-5": "BMI",
}


def _summary_text(doc: dict) -> str:
    name = doc["name"]["full"] or "This patient"
    age = doc.get("age")
    gender = doc.get("gender") or "unknown-gender"
    parts = [f"{name} is a {age}-year-old {gender}." if age is not None else f"{name} ({gender})."]

    active = [
        c for c in doc["conditions"]
        if c.get("clinicalStatus") == "active" and c.get("category") == "clinical"
    ]
    if active:
        names = ", ".join(c["display"] for c in active[:8] if c.get("display"))
        parts.append(f"Active conditions: {names}.")

    meds = [m for m in doc["medications"] if m.get("status") == "active"]
    if meds:
        med_str = ", ".join(
            f"{m['display']}" + (f" ({m['dosageText']})" if m.get("dosageText") else "")
            for m in meds[:8] if m.get("display")
        )
        parts.append(f"Active medications: {med_str}.")

    # latest value per key lab
    latest: dict[str, dict] = {}
    for o in doc["observations"]:
        if o["loinc"] in _KEY_LABS and o["loinc"] not in latest:
            latest[o["loinc"]] = o
    if latest:
        labs = ", ".join(
            f"{_KEY_LABS[k]} {o['value']}{o.get('unit') or ''}"
            + (f" [{o['interpretation']}]" if o.get("interpretation") else "")
            for k, o in latest.items()
        )
        parts.append(f"Recent results: {labs}.")

    if doc["allergies"]:
        allg = ", ".join(a["substance"] for a in doc["allergies"] if a.get("substance"))
        if allg:
            parts.append(f"Allergies: {allg}.")

    if doc["immunizations"]:
        imm = ", ".join(f"{i['vaccine']} ({i['date']})" for i in doc["immunizations"][:4] if i.get("vaccine"))
        if imm:
            parts.append(f"Immunizations: {imm}.")

    if doc["encounters"]:
        last = doc["encounters"][0]
        if last.get("start"):
            parts.append(f"Last seen {last['start']} for {last.get('type') or 'a visit'}.")

    return " ".join(parts)


# --------------------------------- entrypoint -------------------------------

def denormalize(raw: dict) -> dict:
    """Convert a `fhir_raw` bundle document into a denormalized patient document."""
    by = _resources_by_type(raw)
    patient = (by.get("Patient") or [{}])[0]
    patient_id = patient.get("id") or raw.get("_id")

    doc: dict[str, Any] = {
        "_id": patient_id,
        "fhirId": patient_id,
        "source": "fhir_raw",
        **_patient_fields(patient),
        "conditions": _conditions(by.get("Condition", [])),
        "medications": _medications(by.get("MedicationRequest", [])),
        "observations": _observations(by.get("Observation", [])),
        "allergies": _allergies(by.get("AllergyIntolerance", [])),
        "immunizations": _immunizations(by.get("Immunization", [])),
        "encounters": _encounters(by.get("Encounter", [])),
    }
    doc["summaryText"] = _summary_text(doc)
    doc["lastUpdated"] = datetime.now(timezone.utc)
    doc["_denorm"] = {"by": "app", "at": datetime.now(timezone.utc)}
    return doc
