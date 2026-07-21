from backend.app.fhir.denormalizer import denormalize


def test_demographics_and_name_stripping(raw_bundle):
    d = denormalize(raw_bundle)
    assert d["_id"] == "test-pat-001"
    assert d["name"]["full"] == "John Doe"          # Synthea digits stripped
    assert d["gender"] == "male"
    assert d["identifiers"]["mrn"] == "MRN-123"
    assert d["address"]["city"] == "Boston"
    assert d["age"] and d["age"] >= 64


def test_condition_dedup_and_sdoh_tagging(raw_bundle):
    d = denormalize(raw_bundle)
    diabetes = [c for c in d["conditions"] if c["code"] == "44054006"]
    assert len(diabetes) == 1                        # deduped
    assert diabetes[0]["category"] == "clinical"
    social = [c for c in d["conditions"] if c["code"] == "160903007"]
    assert social and social[0]["category"] == "social"


def test_medications(raw_bundle):
    d = denormalize(raw_bundle)
    med = d["medications"][0]
    assert med["rxnorm"] == "860975"
    assert med["status"] == "active"
    assert med["dosageText"] == "500 mg twice daily"
    assert "lastFillDate" not in med                 # refill fields computed at API time


def test_observations_component_expansion(raw_bundle):
    d = denormalize(raw_bundle)
    loincs = {o["loinc"] for o in d["observations"]}
    assert {"4548-4", "8480-6", "8462-4"} <= loincs   # BP split into systolic/diastolic


def test_summary_text(raw_bundle):
    d = denormalize(raw_bundle)
    s = d["summaryText"]
    assert "Type 2 diabetes" in s
    assert "Metformin" in s
    assert "A1c 9.1%" in s
    assert "employment" not in s.lower()             # SDOH excluded from summary
