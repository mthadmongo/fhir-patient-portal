"""Read-time pharmacy helpers (refill/adherence).

Synthea omits `dispenseRequest`, so fill/refill data is synthesized
deterministically per (patientId, rxnorm). This lives outside the denormalizer
so both the app-side path and the Atlas Stream Processor produce identical
`patients` documents (neither stores derived refill fields); pharmacy tenants
compute this on demand.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

DEFAULT_DAYS_SUPPLY = 30


def refill_info(patient_id: str, rxnorm: str, status: str | None,
                today: date | None = None) -> dict:
    """Deterministic fill/refill status for one medication."""
    today = today or date.today()
    days_supply = DEFAULT_DAYS_SUPPLY
    if status != "active":
        return {
            "daysSupply": days_supply, "refillsRemaining": 0,
            "lastFillDate": None, "nextRefillDue": None, "status": "inactive",
        }
    h = int(hashlib.md5(f"{patient_id}:{rxnorm}".encode()).hexdigest(), 16)
    offset = h % (days_supply + 15)      # 0..44 days since last fill
    refills = (h >> 8) % 6               # 0..5 refills remaining
    last_fill = today - timedelta(days=offset)
    next_due = last_fill + timedelta(days=days_supply)
    days_until = (next_due - today).days
    if days_until < 0:
        refill_status = "overdue"
    elif days_until <= 7:
        refill_status = "due_soon"
    else:
        refill_status = "ok"
    return {
        "daysSupply": days_supply,
        "refillsRemaining": refills,
        "lastFillDate": last_fill.isoformat(),
        "nextRefillDue": next_due.isoformat(),
        "daysUntilRefill": days_until,
        "status": refill_status,
    }


def enrich_medication(patient_id: str, med: dict, today: date | None = None) -> dict:
    """Return a copy of `med` with refill fields merged in."""
    info = refill_info(patient_id, med.get("rxnorm", ""), med.get("status"), today)
    return {**med, **info, "medStatus": med.get("status")}
