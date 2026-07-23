#!/usr/bin/env python3
"""Create / start / stop / drop the FHIR denormalization stream processor.

Generates a mongosh script from `pipeline.asp_pipeline()` and runs it against the
SPI. Credentials come from `MongoDB_URI_ALL` via `asp_uri.build_asp_uri()` and are
passed to mongosh as an argument (never written to disk).

Usage:
    python streaming/deploy_processor.py deploy   # drop + create + start
    python streaming/deploy_processor.py create
    python streaming/deploy_processor.py start
    python streaming/deploy_processor.py stop
    python streaming/deploy_processor.py drop
    python streaming/deploy_processor.py status
    python streaming/deploy_processor.py sample   # print a few output docs (sp.sample)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from bson import json_util

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asp_uri import build_asp_uri  # noqa: E402
from pipeline import CONNECTION, DB, DLQ_COLL, asp_pipeline  # noqa: E402

PROCESSOR = "fhirDenormalize"
MONGOSH = "mongosh"


def _run_js(js: str) -> int:
    uri = build_asp_uri()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
        path = f.name
    try:
        return subprocess.run([MONGOSH, uri, "--quiet", path]).returncode
    finally:
        Path(path).unlink(missing_ok=True)


def _pipeline_js() -> str:
    return f"EJSON.parse({json.dumps(json_util.dumps(asp_pipeline()))})"


def _drop_js() -> str:
    return (
        f"try {{ sp.{PROCESSOR}.drop(); print('dropped existing {PROCESSOR}'); }} "
        f"catch (e) {{ print('no existing processor to drop'); }}\n"
    )


def create(start: bool = False) -> int:
    dlq = json.dumps({"connectionName": CONNECTION, "db": DB, "coll": DLQ_COLL})
    js = _drop_js() + (
        f"sp.createStreamProcessor('{PROCESSOR}', {_pipeline_js()}, {{ dlq: {dlq} }});\n"
        f"print('created {PROCESSOR}');\n"
    )
    if start:
        js += f"sp.{PROCESSOR}.start(); print('started {PROCESSOR}');\n"
    return _run_js(js)


def start() -> int:
    return _run_js(f"sp.{PROCESSOR}.start(); print('started {PROCESSOR}');")


def stop() -> int:
    return _run_js(f"sp.{PROCESSOR}.stop(); print('stopped {PROCESSOR}');")


def drop() -> int:
    return _run_js(_drop_js())


def status() -> int:
    return _run_js(
        "printjson(sp.listStreamProcessors());\n"
        f"try {{ printjson(sp.{PROCESSOR}.stats()); }} catch (e) {{ print(e); }}\n"
    )


def sample() -> int:
    return _run_js(f"sp.{PROCESSOR}.sample();")


ACTIONS = {
    "deploy": lambda: create(start=True),
    "create": lambda: create(start=False),
    "start": start,
    "stop": stop,
    "drop": drop,
    "status": status,
    "sample": sample,
}


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action not in ACTIONS:
        print(f"Unknown action '{action}'. Options: {', '.join(ACTIONS)}")
        sys.exit(2)
    sys.exit(ACTIONS[action]())


if __name__ == "__main__":
    main()
