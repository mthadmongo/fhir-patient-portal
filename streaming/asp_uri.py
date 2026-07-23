#!/usr/bin/env python3
"""Print the Atlas Stream Processing (SPI) connection URI.

Reuses the DB-user credentials from `MongoDB_URI_ALL` and injects them into the
SPI host, so the SPI URI never has to be written down with credentials. The
output is meant to be captured into an env var, e.g.:

    export ASP_URI="$(python3 streaming/asp_uri.py)"
    mongosh "$ASP_URI" --eval "sp.listStreamProcessors()"
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from dotenv import load_dotenv

# Load repo-root .env so the streaming scripts pick up secrets the same way the
# backend does (config.py). No-op if the file is absent (e.g. Cloud Agent).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# SPI host for instance `fhir-asp` (region virginia-usa). Override via ASP_HOST.
DEFAULT_ASP_HOST = (
    "atlas-stream-6a5fc7966d7a84f20587fa00-o2ium.virginia-usa.a.query.mongodb.net"
)


def build_asp_uri() -> str:
    src = os.environ["MongoDB_URI_ALL"]
    parts = urlsplit(src)
    user = parts.username or ""
    password = parts.password or ""
    host = os.getenv("ASP_HOST", DEFAULT_ASP_HOST)
    creds = f"{quote_plus(user)}:{quote_plus(password)}@" if user else ""
    return f"mongodb://{creds}{host}/?ssl=true&authSource=admin"


if __name__ == "__main__":
    print(build_asp_uri())
