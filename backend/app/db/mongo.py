"""Singleton MongoDB client + collection accessors.

A single MongoClient is created once and reused across the app (pymongo pools
connections internally). Never instantiate per-request.
"""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from ..config import get_settings

# Collection names
FHIR_RAW = "fhir_raw"
PATIENTS = "patients"
INGEST_STATE = "ingest_state"
DLQ_FHIR = "dlq_fhir"


@lru_cache
def get_client() -> MongoClient:
    s = get_settings()
    return MongoClient(
        s.mongodb_uri,
        maxPoolSize=s.mongo_max_pool_size,
        minPoolSize=s.mongo_min_pool_size,
        connectTimeoutMS=10_000,      # fail fast on connect issues
        socketTimeoutMS=30_000,       # short OLTP ops; prevent hanging sockets
        serverSelectionTimeoutMS=5_000,  # quick failover on topology changes
        retryWrites=True,
        appname="fhir-patient-portal",
    )


def get_db() -> Database:
    return get_client()[get_settings().db_name]


def collection(name: str) -> Collection:
    return get_db()[name]
