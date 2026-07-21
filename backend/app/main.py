"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.mongo import get_client, get_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi-Tenant FHIR Patient Portal",
        version="0.1.0",
        description="RAG chatbot over FHIR patient data stored in MongoDB Atlas.",
    )

    # Local demo: allow the Vite dev server (and everything else) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health() -> dict:
        client = get_client()
        client.admin.command("ping")
        db = get_db()
        return {
            "status": "ok",
            "db": db.name,
            "collections": db.list_collection_names(),
        }

    @app.get("/", tags=["system"])
    def root() -> dict:
        s = get_settings()
        return {
            "app": "Multi-Tenant FHIR Patient Portal",
            "db": s.db_name,
            "llm_model": s.llm_model,
            "voyage_model": s.voyage_model,
        }

    return app


app = create_app()
