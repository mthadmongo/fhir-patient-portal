"""Shared fixtures: a small synthetic FHIR bundle (no DB/network needed)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

PATIENT_ID = "test-pat-001"


def _entry(resource: dict) -> dict:
    return {"resource": resource}


@pytest.fixture
def raw_bundle() -> dict:
    entries = [
        _entry({
            "resourceType": "Patient", "id": PATIENT_ID,
            "identifier": [{"type": {"coding": [{"code": "MR"}]}, "value": "MRN-123"}],
            "name": [{"given": ["John7"], "family": "Doe42"}],
            "gender": "male", "birthDate": "1960-06-15",
            "address": [{"city": "Boston", "state": "MA", "postalCode": "02118"}],
        }),
        _entry({
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006",
                                 "display": "Type 2 diabetes mellitus (disorder)"}]},
            "onsetDateTime": "2015-01-01T00:00:00Z",
        }),
        _entry({  # duplicate diabetes to exercise dedup
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006",
                                 "display": "Type 2 diabetes mellitus (disorder)"}]},
            "onsetDateTime": "2016-01-01T00:00:00Z",
        }),
        _entry({  # SDOH condition -> tagged social
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "160903007",
                                 "display": "Full-time employment (finding)"}]},
            "onsetDateTime": "2010-01-01T00:00:00Z",
        }),
        _entry({
            "resourceType": "MedicationRequest", "status": "active",
            "medicationCodeableConcept": {"coding": [{"system": "rxnorm", "code": "860975",
                                                       "display": "Metformin 500 MG"}]},
            "authoredOn": "2023-01-01T00:00:00Z",
            "dosageInstruction": [{"text": "500 mg twice daily"}],
        }),
        _entry({
            "resourceType": "Observation", "status": "final",
            "category": [{"coding": [{"code": "laboratory"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}]},
            "effectiveDateTime": "2024-05-01T00:00:00Z",
            "valueQuantity": {"value": 9.1, "unit": "%"},
        }),
        _entry({  # blood pressure with components
            "resourceType": "Observation", "status": "final",
            "category": [{"coding": [{"code": "vital-signs"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure"}]},
            "effectiveDateTime": "2024-05-01T00:00:00Z",
            "component": [
                {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic BP"}]},
                 "valueQuantity": {"value": 150, "unit": "mmHg"}},
                {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic BP"}]},
                 "valueQuantity": {"value": 95, "unit": "mmHg"}},
            ],
        }),
        _entry({
            "resourceType": "Immunization", "status": "completed",
            "vaccineCode": {"text": "Influenza, seasonal"},
            "occurrenceDateTime": "2025-10-01T00:00:00Z",
        }),
        _entry({
            "resourceType": "Encounter", "class": {"code": "AMB"},
            "type": [{"coding": [{"display": "General examination (procedure)"}]}],
            "period": {"start": "2024-05-01T00:00:00Z"},
            "participant": [{"individual": {"display": "Dr. Smith"}}],
        }),
    ]
    return {
        "_id": PATIENT_ID, "resourceType": "Bundle", "type": "transaction",
        "entry": entries, "_ingest": {"loadedAt": datetime.now(timezone.utc)},
    }
