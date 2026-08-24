"""Smoke test contra el servidor en ejecución (requiere el backend arrancado).

Uso:
    .venv\\Scripts\\python.exe scripts/smoke_test.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str, timeout: int = 15) -> bool:
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            print(f"[OK]   GET {path} -> {r.status}")
            return r.status == 200
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] GET {path} -> {exc}")
        return False


def tts_works() -> bool:
    req = urllib.request.Request(
        BASE + "/api/tts",
        data=json.dumps({"text": "Hello"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            ok = r.status == 200 and body.startswith(b"RIFF") and len(body) > 44
            label = "OK" if ok else "FAIL"
            print(f"[{label}]   POST /api/tts -> {r.status} ({len(body)} bytes)")
            return ok
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] POST /api/tts -> {exc}")
        return False


def main() -> int:
    results = [
        get("/"),
        get("/api/health"),
        get("/api/models"),
        tts_works(),
    ]
    print()
    if all(results):
        print("SMOKE PASSED")
        return 0
    print("SMOKE FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
