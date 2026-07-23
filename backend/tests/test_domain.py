from datetime import date

from backend.app.domain import interactions, labs, payer, pharmacy
from backend.app.fhir.denormalizer import denormalize
from backend.app.fhir.pharmacy import refill_info


def test_refill_info_deterministic_and_status():
    a = refill_info("p1", "860975", "active", today=date(2026, 7, 21))
    b = refill_info("p1", "860975", "active", today=date(2026, 7, 21))
    assert a == b                                   # deterministic
    assert a["status"] in ("ok", "due_soon", "overdue")
    inactive = refill_info("p1", "860975", "completed")
    assert inactive["status"] == "inactive" and inactive["refillsRemaining"] == 0


def test_drug_interactions():
    meds = [
        {"display": "Warfarin 5 MG", "status": "active"},
        {"display": "Aspirin 81 MG", "status": "active"},
        {"display": "Levothyroxine 50 MCG", "status": "active"},
    ]
    found = interactions.check_interactions(meds)
    assert any(f["severity"] == "major" for f in found)


def test_payer_risk_and_care_gaps(raw_bundle):
    p = denormalize(raw_bundle)
    risk = payer.risk_score(p)
    assert risk["riskScore"] >= 3                    # diabetes contributes
    gaps = payer.care_gaps(p)
    # A1c 9.1 (>8) should be an open HbA1c control gap
    assert any(g["measure"].startswith("HbA1c Control") and g["status"] == "open"
               for g in gaps["careGaps"])


def test_labs_abnormal_and_trends(raw_bundle):
    p = denormalize(raw_bundle)
    ab = labs.abnormal_flags(p)
    flagged = {a["loinc"] for a in ab["abnormal"]}
    assert "4548-4" in flagged                        # A1c 9.1 flagged High
    trend = labs.lab_trends(p, "4548-4")
    assert trend["count"] == 1 and trend["label"] == "Hemoglobin A1c"


def test_pharmacy_adherence(raw_bundle):
    p = denormalize(raw_bundle)
    adh = pharmacy.adherence(p)
    assert adh["adherenceScore"] is not None
    assert "Metformin 500 MG" in adh["medSyncCandidates"]
