#!/usr/bin/env python3
"""Generate a pool of synthetic FHIR R4 patients with Synthea.

Downloads the Synthea jar on first run, then emits patient bundles to
`data/synthea/output/fhir/`. These bundles are the source pool that the
Load-Batch ingest reads from (10 patients per batch).

Usage:
    python scripts/gen_synthea.py --count 100 --seed 20240721
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JAR_PATH = REPO_ROOT / "tools" / "synthea.jar"
OUTPUT_DIR = REPO_ROOT / "data" / "synthea" / "output"
JAR_URL = (
    "https://github.com/synthetichealth/synthea/releases/latest/download/"
    "synthea-with-dependencies.jar"
)


def ensure_jar() -> None:
    if JAR_PATH.exists():
        return
    JAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Synthea jar to {JAR_PATH} ...")
    urllib.request.urlretrieve(JAR_URL, JAR_PATH)
    print("Done.")


def generate(count: int, seed: int, state: str) -> None:
    ensure_jar()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "java", "-jar", str(JAR_PATH),
        "-p", str(count),
        "-s", str(seed),
        "--exporter.baseDirectory", str(OUTPUT_DIR),
        "--exporter.fhir.export", "true",
        "--exporter.hospital.fhir.export", "false",
        "--exporter.practitioner.fhir.export", "false",
        state,
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    files = list((OUTPUT_DIR / "fhir").glob("*.json"))
    print(f"Generated {len(files)} patient bundles in {OUTPUT_DIR / 'fhir'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic FHIR patients with Synthea")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20240721)
    ap.add_argument("--state", default="Massachusetts")
    args = ap.parse_args()
    generate(args.count, args.seed, args.state)


if __name__ == "__main__":
    main()
