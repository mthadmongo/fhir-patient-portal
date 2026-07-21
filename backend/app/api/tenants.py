"""Tenant login / discovery endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..tenants.deps import current_tenant
from ..tenants.registry import get_tenant, list_tenants, tenant_features

router = APIRouter(prefix="/api", tags=["tenants"])


class LoginRequest(BaseModel):
    tenantId: str


@router.get("/tenants")
def tenants() -> list[dict]:
    return list_tenants()


@router.post("/login")
def login(req: LoginRequest) -> dict:
    if not get_tenant(req.tenantId):
        raise HTTPException(status_code=404, detail=f"Unknown tenant '{req.tenantId}'.")
    return tenant_features(req.tenantId)


@router.get("/me")
def me(tenant: dict = Depends(current_tenant)) -> dict:
    return tenant_features(tenant["id"])
