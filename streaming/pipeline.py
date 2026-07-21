"""FHIR bundle -> denormalized patient, as a MongoDB aggregation pipeline.

This is the *streaming* implementation of the transform. The same stages are:
  - tested offline via `db.fhir_raw.aggregate(transform_stages())` (pymongo), and
  - wrapped with a change-stream `$source` + `$merge` to run inside Atlas Stream
    Processing (see `asp_pipeline()` / `deploy_processor.js`).

It mirrors `backend/app/fhir/denormalizer.py`. A few Python-only bits (md5 refill
synthesis) are intentionally computed at API time instead, so this transform and
the app-side one produce identical `patients` documents.
"""
from __future__ import annotations

# SDOH keywords -> a single case-insensitive regex (no regex-special chars).
_SDOH_REGEX = "|".join([
    "employment", "education", "school", "social contact", "social isolation",
    "housing", "criminal record", "refugee", "immigrant", "unemploy",
    "labor force", "risk activity", "transport", "victim", "violence",
    "medication review due", "higher education", "primary school",
    "part-time", "full-time", "part time", "full time", "retired",
    "certificate of high school", "sexually active", "received ",
])

_KEY_LABS = [
    ["4548-4", "A1c"], ["2339-0", "Glucose"], ["2093-3", "Total cholesterol"],
    ["2571-8", "Triglycerides"], ["6299-2", "BUN"], ["38483-4", "Creatinine"],
    ["8480-6", "Systolic BP"], ["8462-4", "Diastolic BP"], ["39156-5", "BMI"],
]


# ------------------------------- expr helpers -------------------------------

def _first(arr):
    return {"$arrayElemAt": [arr, 0]}


def _date10(expr):
    return {"$cond": [{"$eq": [{"$type": expr}, "string"]}, {"$substrBytes": [expr, 0, 10]}, None]}


def _ifnull(expr, alt):
    return {"$ifNull": [expr, alt]}


def _system_short(sysexpr):
    def m(pat):
        return {"$regexMatch": {"input": _ifnull(sysexpr, ""), "regex": pat}}
    return {"$switch": {"branches": [
        {"case": m("snomed"), "then": "snomed"},
        {"case": m("loinc"), "then": "loinc"},
        {"case": m("rxnorm"), "then": "rxnorm"},
        {"case": m("cvx"), "then": "cvx"},
    ], "default": _ifnull(sysexpr, "")}}


def _strip_digits(expr):
    """Take the leading non-digit run of a name token (Synthea appends digits)."""
    return _ifnull(
        {"$getField": {"field": "match", "input": {"$regexFind": {"input": _ifnull(expr, ""), "regex": "[^0-9]+"}}}},
        expr,
    )


def _join_space(arr):
    return {"$reduce": {
        "input": arr, "initialValue": "",
        "in": {"$cond": [{"$eq": ["$$value", ""]}, "$$this", {"$concat": ["$$value", " ", "$$this"]}]},
    }}


def _cat_list(ovar):
    """Flatten an Observation's category codes into a single string array."""
    return {"$reduce": {
        "input": _ifnull(ovar + ".category", []), "initialValue": [],
        "in": {"$concatArrays": ["$$value", _ifnull("$$this.coding.code", [])]},
    }}


# ------------------------------- transform ----------------------------------

def transform_stages() -> list[dict]:
    # Stage 1: resources array
    s1 = {"$addFields": {"_resources": _ifnull("$entry.resource", [])}}

    def by_type(rt):
        return {"$filter": {"input": "$_resources", "as": "r", "cond": {"$eq": ["$$r.resourceType", rt]}}}

    # Stage 2: split resources by type
    s2 = {"$addFields": {
        "_patient": {"$first": by_type("Patient")},
        "_conditionsR": by_type("Condition"),
        "_medsR": by_type("MedicationRequest"),
        "_obsR": by_type("Observation"),
        "_immR": by_type("Immunization"),
        "_encR": by_type("Encounter"),
        "_allergyR": by_type("AllergyIntolerance"),
    }}

    # given/family from patient name[0]
    given_arr = {"$map": {"input": _ifnull({"$first": "$_patient.name.given"}, []), "as": "g",
                          "in": _strip_digits("$$g")}}
    given_full = _join_space(given_arr)
    family = _strip_digits({"$first": "$_patient.name.family"})

    mrn = {"$let": {"vars": {"mr": {"$first": {"$filter": {
        "input": _ifnull("$_patient.identifier", []), "as": "id",
        "cond": {"$eq": [{"$first": "$$id.type.coding.code"}, "MR"]}}}}},
        "in": "$$mr.value"}}

    addr0 = {"$first": "$_patient.address"}

    age = {"$let": {"vars": {
        "bd": {"$dateFromString": {"dateString": _ifnull("$_patient.birthDate", ""), "onError": None}},
        "now": _ifnull("$_ingest.loadedAt", None)},
        "in": {"$cond": [{"$and": [{"$ne": ["$$bd", None]}, {"$ne": ["$$now", None]}]},
                         {"$let": {"vars": {
                             "hadBirthday": {"$gte": [
                                 {"$add": [{"$multiply": [{"$month": "$$now"}, 100]}, {"$dayOfMonth": "$$now"}]},
                                 {"$add": [{"$multiply": [{"$month": "$$bd"}, 100]}, {"$dayOfMonth": "$$bd"}]}]}},
                             "in": {"$subtract": [{"$subtract": [{"$year": "$$now"}, {"$year": "$$bd"}]},
                                                  {"$cond": ["$$hadBirthday", 0, 1]}]}}},
                         None]}}}

    # conditions
    conditions = {"$map": {"input": "$_conditionsR", "as": "r", "in": {"$let": {
        "vars": {"disp": _ifnull({"$first": "$$r.code.coding.display"}, "$$r.code.text")},
        "in": {
            "code": {"$first": "$$r.code.coding.code"},
            "system": _system_short({"$first": "$$r.code.coding.system"}),
            "display": "$$disp",
            "clinicalStatus": {"$first": "$$r.clinicalStatus.coding.code"},
            "onsetDate": _date10(_ifnull("$$r.onsetDateTime", "$$r.recordedDate")),
            "category": {"$cond": [{"$regexMatch": {"input": _ifnull("$$disp", ""), "regex": _SDOH_REGEX, "options": "i"}},
                                   "social", "clinical"]},
        }}}}}

    # medications
    medications = {"$map": {"input": "$_medsR", "as": "r", "in": {
        "rxnorm": {"$first": "$$r.medicationCodeableConcept.coding.code"},
        "display": _ifnull({"$first": "$$r.medicationCodeableConcept.coding.display"},
                           "$$r.medicationCodeableConcept.text"),
        "status": "$$r.status",
        "authoredOn": _date10("$$r.authoredOn"),
        "dosageText": _ifnull({"$first": "$$r.dosageInstruction.text"}, ""),
    }}}

    # observations (flatten valueQuantity + components), lab/vital only, sorted desc
    def obs_record(ovar, codeholder, valueholder):
        cats = _cat_list(ovar)
        return {
            "loinc": {"$first": f"{codeholder}.code.coding.code"},
            "display": _ifnull({"$first": f"{codeholder}.code.coding.display"}, f"{codeholder}.code.text"),
            "value": f"{valueholder}.valueQuantity.value",
            "unit": f"{valueholder}.valueQuantity.unit",
            "effectiveDate": _date10(_ifnull(f"{ovar}.effectiveDateTime", f"{ovar}.issued")),
            "interpretation": {"$let": {"vars": {"i0": {"$first": f"{ovar}.interpretation"}},
                                        "in": {"$first": "$$i0.coding.code"}}},
            "category": {"$cond": [{"$in": ["laboratory", cats]}, "laboratory", "vital-signs"]},
        }

    obs_flat = {"$reduce": {
        "input": "$_obsR", "initialValue": [],
        "in": {"$concatArrays": ["$$value", {"$let": {
            "vars": {"o": "$$this", "cats": _cat_list("$$this")},
            "in": {"$cond": [
                {"$or": [{"$in": ["laboratory", "$$cats"]}, {"$in": ["vital-signs", "$$cats"]}]},
                {"$cond": [
                    {"$ne": [{"$type": "$$o.valueQuantity"}, "missing"]},
                    [obs_record("$$o", "$$o", "$$o")],
                    {"$cond": [
                        {"$ne": [{"$type": "$$o.component"}, "missing"]},
                        {"$map": {"input": "$$o.component", "as": "c", "in": obs_record("$$o", "$$c", "$$c")}},
                        [],
                    ]},
                ]},
                [],
            ]},
        }}]},
    }}
    observations = {"$sortArray": {"input": obs_flat, "sortBy": {"effectiveDate": -1}}}

    immunizations = {"$map": {"input": "$_immR", "as": "r", "in": {
        "vaccine": _ifnull("$$r.vaccineCode.text", {"$first": "$$r.vaccineCode.coding.display"}),
        "date": _date10("$$r.occurrenceDateTime"),
    }}}

    encounters = {"$sortArray": {"input": {"$map": {"input": "$_encR", "as": "r", "in": {
        "type": {"$let": {"vars": {"t0": {"$first": "$$r.type"}},
                          "in": _ifnull({"$first": "$$t0.coding.display"}, "$$t0.text")}},
        "class": "$$r.class.code",
        "start": _date10("$$r.period.start"),
        "provider": _ifnull({"$first": "$$r.participant.individual.display"}, "$$r.serviceProvider.display"),
    }}}, "sortBy": {"start": -1}}}

    allergies = {"$map": {"input": "$_allergyR", "as": "r", "in": {
        "substance": _ifnull({"$first": "$$r.code.coding.display"}, "$$r.code.text"),
        "reaction": {"$let": {"vars": {"r0": {"$first": "$$r.reaction"}}, "in": {"$let": {
            "vars": {"m0": {"$first": "$$r0.manifestation"}},
            "in": _ifnull({"$first": "$$m0.coding.display"}, "$$m0.text")}}}},
        "severity": {"$let": {"vars": {"r0": {"$first": "$$r.reaction"}}, "in": "$$r0.severity"}},
    }}}

    # Stage 3: build denormalized fields
    s3 = {"$addFields": {
        "fhirId": "$_patient.id",
        "source": "fhir_raw",
        "identifiers": {"mrn": mrn},
        "name": {"full": {"$trim": {"input": {"$concat": [given_full, " ", _ifnull(family, "")]}}},
                 "given": given_full, "family": family},
        "gender": "$_patient.gender",
        "birthDate": _date10("$_patient.birthDate"),
        "age": age,
        "address": {"$let": {"vars": {"a": addr0}, "in": {
            "city": "$$a.city", "state": "$$a.state", "postalCode": "$$a.postalCode"}}},
        "conditions": conditions,
        "medications": medications,
        "observations": observations,
        "immunizations": immunizations,
        "encounters": encounters,
        "allergies": allergies,
    }}

    # Stage 3b: dedup conditions (by code) and medications (by rxnorm), then sort
    s3b = {"$addFields": {
        "conditions": {"$sortArray": {
            "input": _dedup("$conditions", "code", "onsetDate", 1, "clinicalStatus"),
            "sortBy": {"onsetDate": 1}}},
        "medications": {"$sortArray": {
            "input": _dedup("$medications", "rxnorm", "authoredOn", -1, "status"),
            "sortBy": {"authoredOn": -1}}},
    }}

    # Stage 4: summaryText from stage-3 fields
    active_clinical = {"$filter": {"input": "$conditions", "as": "c",
        "cond": {"$and": [{"$eq": ["$$c.clinicalStatus", "active"]}, {"$eq": ["$$c.category", "clinical"]}]}}}
    active_meds = {"$filter": {"input": "$medications", "as": "m", "cond": {"$eq": ["$$m.status", "active"]}}}

    cond_str = _join_comma({"$map": {"input": {"$slice": [active_clinical, 8]}, "as": "c", "in": "$$c.display"}})
    med_str = _join_comma({"$map": {"input": {"$slice": [active_meds, 8]}, "as": "m", "in": {
        "$concat": ["$$m.display", {"$cond": [{"$gt": [{"$strLenCP": _ifnull("$$m.dosageText", "")}, 0]},
                                              {"$concat": [" (", "$$m.dosageText", ")"]}, ""]}]}}})
    lab_str = _join_comma({"$map": {"input": _KEY_LABS, "as": "kl", "in": {"$let": {
        "vars": {"hit": {"$first": {"$filter": {"input": "$observations", "as": "o",
                                                "cond": {"$eq": ["$$o.loinc", {"$arrayElemAt": ["$$kl", 0]}]}}}}},
        "in": {"$cond": [{"$and": [{"$ne": ["$$hit", None]}, {"$ne": [_ifnull("$$hit.value", None), None]}]},
                         {"$concat": [{"$arrayElemAt": ["$$kl", 1]}, " ",
                                      {"$toString": _ifnull("$$hit.value", "")}, _ifnull("$$hit.unit", "")]},
                         None]}}}}})
    allergy_str = _join_comma({"$map": {"input": "$allergies", "as": "a", "in": "$$a.substance"}})
    last_enc = {"$first": "$encounters"}

    summary = {"$trim": {"input": {"$concat": [
        _ifnull("$name.full", "Patient"),
        {"$cond": [{"$ne": ["$age", None]},
                   {"$concat": [" is a ", {"$toString": "$age"}, "-year-old ", _ifnull("$gender", ""), "."]},
                   {"$concat": [" (", _ifnull("$gender", ""), ")."]}]},
        {"$cond": [{"$gt": [{"$strLenCP": cond_str}, 0]}, {"$concat": [" Active conditions: ", cond_str, "."]}, ""]},
        {"$cond": [{"$gt": [{"$strLenCP": med_str}, 0]}, {"$concat": [" Active medications: ", med_str, "."]}, ""]},
        {"$cond": [{"$gt": [{"$strLenCP": lab_str}, 0]}, {"$concat": [" Recent results: ", lab_str, "."]}, ""]},
        {"$cond": [{"$gt": [{"$strLenCP": allergy_str}, 0]}, {"$concat": [" Allergies: ", allergy_str, "."]}, ""]},
        {"$cond": [{"$ne": [_ifnull("$$le.start", None), None]},
                   {"$concat": [" Last seen ", "$$le.start", " for ", _ifnull("$$le.type", "a visit"), "."]}, ""]},
    ]}}}
    s4 = {"$addFields": {"summaryText": {"$let": {"vars": {"le": last_enc}, "in": summary}},
                         "lastUpdated": _ifnull("$_ingest.loadedAt", None),
                         "_denorm": {"by": "asp"}}}

    # Stage 5: final projection
    s5 = {"$project": {
        "_id": "$_patient.id", "fhirId": 1, "source": 1, "identifiers": 1, "name": 1,
        "gender": 1, "birthDate": 1, "age": 1, "address": 1, "conditions": 1, "medications": 1,
        "observations": 1, "immunizations": 1, "encounters": 1, "allergies": 1,
        "summaryText": 1, "lastUpdated": 1, "_denorm": 1,
    }}

    return [s1, s2, s3, s3b, s4, s5]


DB = "patient_portal"
CONNECTION = "fhirCluster"
SOURCE_COLL = "fhir_raw"
SINK_COLL = "patients"
DLQ_COLL = "dlq_asp"


def asp_pipeline() -> list[dict]:
    """Full Atlas Stream Processing pipeline: change stream -> denormalize -> merge."""
    source = {"$source": {
        "connectionName": CONNECTION, "db": DB, "coll": SOURCE_COLL,
        "config": {"fullDocument": "updateLookup"},
    }}
    match = {"$match": {
        "operationType": {"$in": ["insert", "replace", "update"]},
        "fullDocument": {"$exists": True},
    }}
    unwrap = {"$replaceRoot": {"newRoot": "$fullDocument"}}
    merge = {"$merge": {
        "into": {"connectionName": CONNECTION, "db": DB, "coll": SINK_COLL},
        "on": "_id", "whenMatched": "merge", "whenNotMatched": "insert",
    }}
    return [source, match, unwrap, *transform_stages(), merge]


def _dedup(arr_field, key: str, sort_field: str, sort_dir: int, status_field: str):
    """Dedup an array of dicts by `key`, keeping the entry chosen by sort order and
    marking it 'active' if any duplicate is active (mirrors the Python denormalizer)."""
    codes = {"$filter": {
        "input": {"$setUnion": [{"$map": {"input": arr_field, "as": "e", "in": f"$$e.{key}"}}, []]},
        "as": "c", "cond": {"$ne": ["$$c", None]}}}
    return {"$map": {"input": codes, "as": "k", "in": {"$let": {
        "vars": {"grp": {"$filter": {"input": arr_field, "as": "e", "cond": {"$eq": [f"$$e.{key}", "$$k"]}}}},
        "in": {"$let": {"vars": {
            "chosen": {"$first": {"$sortArray": {"input": "$$grp", "sortBy": {sort_field: sort_dir}}}},
            "anyActive": {"$anyElementTrue": {"$map": {"input": "$$grp", "as": "g",
                                                       "in": {"$eq": [f"$$g.{status_field}", "active"]}}}},
        }, "in": {"$mergeObjects": ["$$chosen", {"$cond": ["$$anyActive", {status_field: "active"}, {}]}]}}},
    }}}}


def _join_comma(arr):
    """Join a (possibly null-containing) string array with ', '."""
    clean = {"$filter": {"input": arr, "as": "x", "cond": {"$and": [
        {"$ne": ["$$x", None]}, {"$ne": ["$$x", ""]}]}}}
    return {"$reduce": {"input": clean, "initialValue": "",
                        "in": {"$cond": [{"$eq": ["$$value", ""]}, "$$this",
                                         {"$concat": ["$$value", ", ", "$$this"]}]}}}
