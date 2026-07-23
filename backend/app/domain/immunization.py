"""Immunization eligibility (Walgreens)."""
from __future__ import annotations

from datetime import date


def _years_since(d: str | None, today: date) -> float | None:
    if not d:
        return None
    try:
        y, m, day = (int(x) for x in d[:10].split("-"))
        return (today - date(y, m, day)).days / 365.25
    except Exception:
        return None


def _latest_for(immunizations: list[dict], keyword: str) -> str | None:
    dates = [i["date"] for i in immunizations
             if i.get("vaccine") and keyword in i["vaccine"].lower() and i.get("date")]
    return max(dates) if dates else None


def eligibility(patient: dict, today: date | None = None) -> dict:
    today = today or date.today()
    age = patient.get("age") or 0
    imm = patient.get("immunizations", [])
    recs: list[dict] = []

    def add(vaccine, due, reason):
        recs.append({"vaccine": vaccine, "due": due, "reason": reason})

    flu = _years_since(_latest_for(imm, "influenza"), today)
    add("Influenza (seasonal)", flu is None or flu >= 1,
        "No flu vaccine in the last 12 months." if (flu is None or flu >= 1) else "Up to date.")

    covid = _years_since(_latest_for(imm, "covid"), today)
    add("COVID-19", covid is None or covid >= 1,
        "No COVID-19 vaccine in the last 12 months." if (covid is None or covid >= 1) else "Up to date.")

    if age >= 65:
        pneumo = _latest_for(imm, "pneumococcal")
        add("Pneumococcal", pneumo is None,
            "Age 65+ with no pneumococcal vaccine on record." if pneumo is None else "On record.")
    if age >= 50:
        shingles = _latest_for(imm, "zoster") or _latest_for(imm, "shingles")
        add("Shingles (Zoster)", shingles is None,
            "Age 50+ with no shingles vaccine on record." if shingles is None else "On record.")

    tdap = _years_since(_latest_for(imm, "tdap") or _latest_for(imm, "tetanus"), today)
    add("Tdap/Td booster", tdap is None or tdap >= 10,
        "No tetanus booster in the last 10 years." if (tdap is None or tdap >= 10) else "Up to date.")

    return {
        "patientId": patient["_id"], "age": age,
        "recommended": [r for r in recs if r["due"]],
        "all": recs,
    }
