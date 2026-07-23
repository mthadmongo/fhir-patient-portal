"""Tenant resolution dependencies (very basic click-to-login).

The frontend stores the selected tenant and sends it as the `X-Tenant` header.
No real auth — this is a demo.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from .registry import get_tenant


def current_tenant(x_tenant: str | None = Header(default=None)) -> dict:
    if not x_tenant:
        raise HTTPException(status_code=401, detail="No tenant selected. Log in as a tenant first.")
    tenant = get_tenant(x_tenant)
    if not tenant:
        raise HTTPException(status_code=401, detail=f"Unknown tenant '{x_tenant}'.")
    return tenant


def require_tenant(tenant_id: str):
    """Dependency factory: gate a specialized router to a single tenant."""
    def dependency(x_tenant: str | None = Header(default=None)) -> dict:
        tenant = current_tenant(x_tenant)
        if tenant["id"] != tenant_id:
            raise HTTPException(
                status_code=403,
                detail=f"This API is only available to {tenant_id}; you are logged in as {tenant['id']}.",
            )
        return tenant
    return dependency
