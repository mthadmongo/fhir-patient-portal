"""Embed denormalized patients that don't yet have a vector.

This is the app-side embedding step (approved fallback vs. in-ASP embedding):
after denormalization, patient `summaryText` is embedded with voyage-4 and stored
on the `patients` document as `embedding`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import get_settings
from ..db.mongo import PATIENTS, collection
from .voyage import embed_texts

BATCH = 32


def embed_pending(limit: int | None = None) -> dict[str, int]:
    """Find patients missing an embedding, embed their summaryText, and store it."""
    s = get_settings()
    query = {"embedding": {"$exists": False}, "summaryText": {"$exists": True, "$ne": ""}}
    cursor = collection(PATIENTS).find(query, {"_id": 1, "summaryText": 1})
    if limit:
        cursor = cursor.limit(limit)
    pending = list(cursor)

    embedded, errors = 0, 0
    for i in range(0, len(pending), BATCH):
        chunk = pending[i : i + BATCH]
        try:
            vectors = embed_texts([p["summaryText"] for p in chunk], input_type="document")
        except Exception:  # noqa: BLE001 - keep going; surface count
            errors += len(chunk)
            continue
        for p, vec in zip(chunk, vectors):
            collection(PATIENTS).update_one(
                {"_id": p["_id"]},
                {"$set": {
                    "embedding": vec,
                    "embeddingModel": s.voyage_model,
                    "embeddedAt": datetime.now(timezone.utc),
                }},
            )
            embedded += 1
    return {"embedded": embedded, "errors": errors, "pending": len(pending)}
