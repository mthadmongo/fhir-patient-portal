"""Load-Batch ingest: read Synthea FHIR bundles and insert raw FHIR into `fhir_raw`.

Each `fhir_raw` document is a single patient's FHIR Bundle stored verbatim (the
"we own the raw FHIR" source of truth). A cursor in `ingest_state` tracks which
source files have been loaded so repeated Load-Batch calls stream in more patients.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import BSON

from ..config import get_settings
from ..db.mongo import DLQ_FHIR, FHIR_RAW, INGEST_STATE, PATIENTS, collection
from ..embed.worker import embed_pending
from ..fhir.denormalizer import denormalize

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FHIR_DIR = REPO_ROOT / "data" / "synthea" / "output" / "fhir"

STATE_ID = "loader"
# Stay comfortably under the 16 MB BSON document limit.
MAX_DOC_BYTES = 15_500_000
# Non-clinical / bulky resource types dropped only if a bundle is too large to store.
DROPPABLE_TYPES = {
    "Claim", "ExplanationOfBenefit", "DocumentReference", "ImagingStudy",
    "Provenance", "SupplyDelivery", "Device", "MedicationAdministration",
}


def _fhir_dir() -> Path:
    return Path(os.getenv("DATA_DIR", str(DEFAULT_FHIR_DIR)))


def available_files() -> list[str]:
    """Sorted list of patient bundle filenames (excludes Synthea metadata files)."""
    d = _fhir_dir()
    if not d.exists():
        return []
    files = [
        p.name
        for p in d.glob("*.json")
        if not p.name.startswith(("hospitalInformation", "practitionerInformation"))
    ]
    return sorted(files)


def _get_state() -> dict[str, Any]:
    state = collection(INGEST_STATE).find_one({"_id": STATE_ID})
    return state or {"_id": STATE_ID, "loaded_files": [], "batch_number": 0}


def _extract_patient_id(bundle: dict) -> str | None:
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "Patient":
            return res.get("id")
    return None


def _build_raw_doc(bundle: dict, patient_id: str, batch_number: int, source_file: str) -> dict:
    doc = {
        "_id": patient_id,
        "resourceType": "Bundle",
        "type": bundle.get("type", "collection"),
        "entry": bundle.get("entry", []),
        "_ingest": {
            "loadedAt": datetime.now(timezone.utc),
            "batchNumber": batch_number,
            "sourceFile": source_file,
        },
    }
    # Size guard: if the full bundle exceeds the doc limit, drop bulky non-clinical
    # resources (still valid FHIR, just a trimmed bundle) until it fits.
    if len(BSON.encode(doc)) > MAX_DOC_BYTES:
        doc["entry"] = [
            e for e in doc["entry"]
            if e.get("resource", {}).get("resourceType") not in DROPPABLE_TYPES
        ]
        doc["_ingest"]["trimmed"] = True
    return doc


def _denormalize_and_store(raw_doc: dict) -> None:
    """Denormalize one raw bundle into `patients`, preserving any existing embedding."""
    den = denormalize(raw_doc)
    existing = collection(PATIENTS).find_one({"_id": den["_id"]}, {"embedding": 1})
    if existing and "embedding" in existing:
        den["embedding"] = existing["embedding"]
    collection(PATIENTS).replace_one({"_id": den["_id"]}, den, upsert=True)


def load_batch(size: int = 10) -> dict[str, Any]:
    """Load the next `size` unloaded patient bundles into `fhir_raw`."""
    files = available_files()
    if not files:
        raise FileNotFoundError(
            f"No Synthea bundles found in {_fhir_dir()}. Run scripts/gen_synthea.py first."
        )

    state = _get_state()
    loaded = set(state.get("loaded_files", []))
    remaining = [f for f in files if f not in loaded]

    if not remaining:
        return {
            "loadedPatientIds": [],
            "batchNumber": state.get("batch_number", 0),
            "totalRawLoaded": len(loaded),
            "poolSize": len(files),
            "note": "All patients in the pool have already been loaded.",
        }

    batch_files = remaining[:size]
    batch_number = state.get("batch_number", 0) + 1
    raw = collection(FHIR_RAW)
    dlq = collection(DLQ_FHIR)
    loaded_ids: list[str] = []

    for name in batch_files:
        path = _fhir_dir() / name
        try:
            bundle = json.loads(path.read_text())
            patient_id = _extract_patient_id(bundle)
            if not patient_id:
                raise ValueError("No Patient resource found in bundle")
            doc = _build_raw_doc(bundle, patient_id, batch_number, name)
            raw.replace_one({"_id": patient_id}, doc, upsert=True)
            if get_settings().app_side_denormalize:
                _denormalize_and_store(doc)
            loaded_ids.append(patient_id)
        except Exception as exc:  # noqa: BLE001 - record and continue
            dlq.insert_one({
                "sourceFile": name,
                "error": str(exc),
                "at": datetime.now(timezone.utc),
            })

    collection(INGEST_STATE).update_one(
        {"_id": STATE_ID},
        {
            "$set": {"batch_number": batch_number},
            "$addToSet": {"loaded_files": {"$each": batch_files}},
        },
        upsert=True,
    )

    total_loaded = len(loaded) + len(batch_files)
    embed_result = None
    if get_settings().app_side_denormalize:
        # App-side path: embed the freshly denormalized patients now.
        embed_result = embed_pending()

    return {
        "loadedPatientIds": loaded_ids,
        "batchNumber": batch_number,
        "batchSize": len(batch_files),
        "totalRawLoaded": total_loaded,
        "poolSize": len(files),
        "embedding": embed_result,
        "note": "Stream Processor will denormalize these into `patients` momentarily.",
    }


def ingest_status() -> dict[str, Any]:
    state = _get_state()
    return {
        "poolSize": len(available_files()),
        "loadedFiles": len(state.get("loaded_files", [])),
        "batchNumber": state.get("batch_number", 0),
        "fhirRawCount": collection(FHIR_RAW).estimated_document_count(),
        "patientsCount": collection(PATIENTS).estimated_document_count(),
        "embeddedCount": collection(PATIENTS).count_documents({"embedding": {"$exists": True}}),
    }


def reset_ingest() -> dict[str, Any]:
    """Clear ingest state + loaded raw/denormalized data (demo convenience)."""
    collection(FHIR_RAW).delete_many({})
    collection(PATIENTS).delete_many({})
    collection(INGEST_STATE).delete_many({})
    collection(DLQ_FHIR).delete_many({})
    return {"reset": True}
