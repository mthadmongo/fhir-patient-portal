#!/usr/bin/env python3
"""Seed the demo: load patients (app-side denormalize + embed) and create indexes.

Runs without the API server or the Stream Processor. Useful for a quick setup:

    python scripts/seed.py --patients 40
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.ingest import loader  # noqa: E402


def seed(target: int) -> None:
    status = loader.ingest_status()
    if status["poolSize"] == 0:
        print("No Synthea bundles found. Run scripts/gen_synthea.py first.")
        sys.exit(1)
    while loader.ingest_status()["loadedFiles"] < min(target, status["poolSize"]):
        res = loader.load_batch(10)
        if res.get("batchSize", 0) == 0:
            break
        print(f"Loaded batch {res['batchNumber']}: {res['batchSize']} patients "
              f"(total {res['totalRawLoaded']})")
    print("Final:", loader.ingest_status())

    print("\nCreating search indexes...")
    from scripts.create_indexes import create as create_indexes
    create_indexes()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=40)
    seed(ap.parse_args().patients)
