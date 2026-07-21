"""Application settings loaded from environment (or a local .env file).

Secret env var names match what the Cloud Agent injects:
  MongoDB_URI_ALL, VoyageAI_API_ALL, GROVE_LLM_KEY_ALL
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    mongodb_uri: str
    voyage_api_key: str
    grove_api_key: str

    db_name: str = "patient_portal"

    llm_model: str = "gpt-5.5"
    grove_url: str = (
        "https://grove-gateway-prod.azure-api.net/grove-foundry-prod/openai/v1/responses"
    )

    voyage_model: str = "voyage-4"
    # MongoDB-hosted Voyage endpoint (the injected key is an Atlas model API key,
    # authenticated as a Bearer token). Voyage's public api.voyageai.com rejects it.
    voyage_url: str = "https://ai.mongodb.com/v1/embeddings"
    embedding_dim: int = 1024

    # Mongo pool: local single-instance demo, light/bursty concurrency.
    # maxPoolSize 50 covers the small burst from a Load-Batch call; minPoolSize 5
    # keeps a few warm connections without holding idle capacity on the cluster.
    mongo_max_pool_size: int = 50
    mongo_min_pool_size: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mongodb_uri=os.environ["MongoDB_URI_ALL"],
        voyage_api_key=os.environ["VoyageAI_API_ALL"],
        grove_api_key=os.environ["GROVE_LLM_KEY_ALL"],
        db_name=os.getenv("DB_NAME", "patient_portal"),
        llm_model=os.getenv("LLM_MODEL", "gpt-5.5"),
        grove_url=os.getenv(
            "GROVE_URL",
            "https://grove-gateway-prod.azure-api.net/grove-foundry-prod/openai/v1/responses",
        ),
        voyage_model=os.getenv("VOYAGE_MODEL", "voyage-4"),
        voyage_url=os.getenv("VOYAGE_URL", "https://ai.mongodb.com/v1/embeddings"),
    )
