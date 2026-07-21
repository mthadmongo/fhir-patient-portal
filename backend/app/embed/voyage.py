"""VoyageAI embedding client (via MongoDB's hosted endpoint).

The injected key is a MongoDB Atlas model API key, so requests go to
`https://ai.mongodb.com/v1/embeddings` with Bearer auth. `voyage-4` returns
1024-dimensional vectors.
"""
from __future__ import annotations

import httpx

from ..config import get_settings

# Voyage accepts a list of inputs per request; keep batches modest for the demo.
MAX_BATCH = 64


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().voyage_api_key}",
        "Content-Type": "application/json",
    }


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a list of texts. `input_type` is 'document' (stored) or 'query'."""
    if not texts:
        return []
    s = get_settings()
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            resp = client.post(
                s.voyage_url,
                headers=_headers(),
                json={"input": chunk, "model": s.voyage_model, "input_type": input_type},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            # API preserves input order, but sort by index to be safe.
            data.sort(key=lambda d: d.get("index", 0))
            vectors.extend(d["embedding"] for d in data)
    return vectors


def embed_query(text: str) -> list[float]:
    return embed_texts([text], input_type="query")[0]
