"""Ingest / demo-control endpoints (shared across all tenants)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ingest import loader

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class LoadBatchRequest(BaseModel):
    size: int = Field(default=10, ge=1, le=50)


@router.post("/load-batch")
def load_batch(req: LoadBatchRequest | None = None) -> dict:
    size = req.size if req else 10
    try:
        return loader.load_batch(size=size)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status")
def status() -> dict:
    return loader.ingest_status()


@router.post("/reset")
def reset() -> dict:
    return loader.reset_ingest()
