#!/usr/bin/env python3
"""Create the Atlas Search (full-text) and Vector Search indexes on `patients`.

Idempotent: skips indexes that already exist. Uses pymongo's Atlas Search index
management (works directly against the Atlas cluster).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from pymongo.operations import SearchIndexModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings  # noqa: E402
from backend.app.db.mongo import PATIENTS, collection  # noqa: E402

TEXT_INDEX = "patients_text"
VECTOR_INDEX = "patients_vector"


def _text_model() -> SearchIndexModel:
    string_field = {"type": "string"}
    definition = {
        "mappings": {
            "dynamic": False,
            "fields": {
                "name": {"type": "document", "fields": {"full": string_field}},
                "gender": [{"type": "token"}, {"type": "string"}],
                "summaryText": string_field,
                "conditions": {"type": "document", "fields": {"display": string_field}},
                "medications": {"type": "document", "fields": {"display": string_field}},
                "observations": {"type": "document", "fields": {"display": string_field}},
                "allergies": {"type": "document", "fields": {"substance": string_field}},
                "immunizations": {"type": "document", "fields": {"vaccine": string_field}},
            },
        }
    }
    return SearchIndexModel(definition=definition, name=TEXT_INDEX, type="search")


def _vector_model() -> SearchIndexModel:
    dim = get_settings().embedding_dim
    definition = {
        "fields": [
            {"type": "vector", "path": "embedding", "numDimensions": dim, "similarity": "cosine"},
            {"type": "filter", "path": "gender"},
            {"type": "filter", "path": "age"},
        ]
    }
    return SearchIndexModel(definition=definition, name=VECTOR_INDEX, type="vectorSearch")


def create() -> None:
    coll = collection(PATIENTS)
    existing = {ix["name"] for ix in coll.list_search_indexes()}
    to_create = []
    if TEXT_INDEX not in existing:
        to_create.append(_text_model())
    if VECTOR_INDEX not in existing:
        to_create.append(_vector_model())

    if not to_create:
        print("Both search indexes already exist.")
    else:
        names = coll.create_search_indexes(to_create)
        print("Created search indexes:", names)

    # Wait for them to become queryable.
    print("Waiting for indexes to become queryable...")
    for _ in range(60):
        status = {ix["name"]: ix.get("queryable", False) for ix in coll.list_search_indexes()}
        if status.get(TEXT_INDEX) and status.get(VECTOR_INDEX):
            print("Indexes ready:", status)
            return
        time.sleep(5)
    print("Timed out waiting; current status:",
          {ix["name"]: ix.get("queryable") for ix in coll.list_search_indexes()})


if __name__ == "__main__":
    create()
