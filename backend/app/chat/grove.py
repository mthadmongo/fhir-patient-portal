"""gpt-5.5 client via the Grove gateway (OpenAI /responses API)."""
from __future__ import annotations

import httpx

from ..config import get_settings


def _extract_text(payload: dict) -> str:
    """Pull assistant text out of a /responses payload."""
    if payload.get("output_text"):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    chunks.append(c["text"])
    return "\n".join(chunks).strip()


def respond(input_text: str, instructions: str | None = None,
            max_output_tokens: int = 900) -> str:
    s = get_settings()
    body: dict = {"model": s.llm_model, "input": input_text, "max_output_tokens": max_output_tokens}
    if instructions:
        body["instructions"] = instructions
    with httpx.Client(timeout=120) as client:
        resp = client.post(s.grove_url, headers={"api-key": s.grove_api_key,
                                                 "Content-Type": "application/json"}, json=body)
        resp.raise_for_status()
        return _extract_text(resp.json())
