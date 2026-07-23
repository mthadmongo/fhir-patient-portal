"""Search over `patients`: full-text, vector, and hybrid ($rankFusion)."""
from __future__ import annotations

from ..db.mongo import PATIENTS, collection
from ..embed.voyage import embed_query

TEXT_INDEX = "patients_text"
VECTOR_INDEX = "patients_vector"

TEXT_PATHS = [
    "summaryText", "name.full", "conditions.display",
    "medications.display", "observations.display", "allergies.substance",
    "immunizations.vaccine",
]

# Fields returned by search (embedding excluded — it's large and not useful here).
_PROJECT = {"embedding": 0}


def text_search(query: str, limit: int = 10) -> list[dict]:
    pipeline = [
        {"$search": {"index": TEXT_INDEX,
                     "text": {"query": query, "path": TEXT_PATHS, "fuzzy": {"maxEdits": 1}}}},
        {"$limit": limit},
        {"$addFields": {"score": {"$meta": "searchScore"}}},
        {"$project": _PROJECT},
    ]
    return list(collection(PATIENTS).aggregate(pipeline))


def vector_search(query: str, limit: int = 10) -> list[dict]:
    qv = embed_query(query)
    pipeline = [
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding",
                           "queryVector": qv, "numCandidates": 100, "limit": limit}},
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": _PROJECT},
    ]
    return list(collection(PATIENTS).aggregate(pipeline))


def hybrid_search(query: str, limit: int = 10,
                  vector_weight: float = 0.6, text_weight: float = 0.4) -> list[dict]:
    """Combine vector + full-text results with reciprocal-rank fusion ($rankFusion)."""
    qv = embed_query(query)
    pipeline = [
        {"$rankFusion": {
            "input": {"pipelines": {
                "vectorPipeline": [
                    {"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding",
                                       "queryVector": qv, "numCandidates": 100, "limit": limit}},
                ],
                "fullTextPipeline": [
                    {"$search": {"index": TEXT_INDEX,
                                 "text": {"query": query, "path": TEXT_PATHS, "fuzzy": {"maxEdits": 1}}}},
                    {"$limit": limit},
                ],
            }},
            "combination": {"weights": {"vectorPipeline": vector_weight, "fullTextPipeline": text_weight}},
        }},
        {"$limit": limit},
        {"$addFields": {"score": {"$meta": "score"}}},
        {"$project": _PROJECT},
    ]
    return list(collection(PATIENTS).aggregate(pipeline))
