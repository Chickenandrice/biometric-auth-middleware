#!/usr/bin/env python3
from __future__ import annotations

"""
Smoke-test the relay HTTP path without a real BLE edge device.

``SIM_USER_ID`` is only a string label in the JSON body — it is not a built-in
or magic user. The default below is an arbitrary placeholder; for anything
meaningful, set ``SIM_USER_ID`` to a real ``user_id`` you created (e.g. via the
dashboard or POST /users). Running this script will create/enroll that id in
the database like any other client.

The script POSTs synthetic vectors to ``/relay/enrollment`` then
``/relay/authorize`` (same shapes Web Bluetooth / the SDK would forward).

Usage (API running on 8000):

  python scripts/simulate_edge_relay.py
  set SIM_USER_ID=alice && python scripts/simulate_edge_relay.py

Environment:
  BIOAUTH_URL      default http://127.0.0.1:8000
  BIOAUTH_API_KEY  default dev-api-key-001
  SIM_USER_ID      default local_sim_placeholder (fake id for quick local tests)
"""

import json
import math
import os
import random
import sys
import urllib.error
import urllib.request

_DEFAULT_SIM_USER = "local_sim_placeholder"


def _unit_embedding(dim: int = 64, seed: int = 42) -> list[float]:
    rng = random.Random(seed)
    v = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _post_json(url: str, headers: dict, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode()


def main() -> int:
    base = os.environ.get("BIOAUTH_URL", "http://127.0.0.1:8000").rstrip("/")
    key = os.environ.get("BIOAUTH_API_KEY", "dev-api-key-001")
    user_id = os.environ.get("SIM_USER_ID", _DEFAULT_SIM_USER).strip() or _DEFAULT_SIM_USER

    emb = _unit_embedding()
    ts = "2026-03-21T12:00:00Z"
    enroll_body = {
        "user_id": user_id,
        "mode": "enroll",
        "embedding": emb,
        "bpm": 74.0,
        "hrv": 40.0,
        "signal_quality": 0.95,
        "timestamp": ts,
    }
    verify_body = {
        "user_id": user_id,
        "mode": "verify",
        "embedding": emb,
        "bpm": 74.0,
        "hrv": 40.0,
        "signal_quality": 0.95,
        "timestamp": ts,
    }
    auth_body = {
        "user_id": user_id,
        "action": "transfer",
        "risk_level": "high",
        "verification": verify_body,
    }

    h = {"X-API-Key": key, "Accept": "application/json"}

    print(f"URL: {base}  user: {user_id}")
    print("---")

    try:
        req = urllib.request.Request(f"{base}/health")
        with urllib.request.urlopen(req, timeout=10) as r:
            print("GET /health OK:", r.read().decode().strip())
    except urllib.error.URLError as e:
        print("GET /health FAILED:", e, file=sys.stderr)
        print(
            "Start the API:  python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000",
            file=sys.stderr,
        )
        return 1

    try:
        code, body = _post_json(f"{base}/relay/enrollment", h, enroll_body)
        print(f"POST /relay/enrollment -> {code}")
        print(json.dumps(json.loads(body), indent=2))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"POST /relay/enrollment FAILED: {e.code}", file=sys.stderr)
        print(err_body[:1200], file=sys.stderr)
        try:
            detail = json.loads(err_body).get("detail")
            if detail:
                print("\nDetail:", detail, file=sys.stderr)
        except (json.JSONDecodeError, TypeError):
            pass
        return 1

    print("---")

    try:
        code, body = _post_json(f"{base}/relay/authorize", h, auth_body)
        print(f"POST /relay/authorize -> {code}")
        print(json.dumps(json.loads(body), indent=2))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"POST /relay/authorize FAILED: {e.code}", file=sys.stderr)
        print(err_body[:1200], file=sys.stderr)
        return 1

    print("---")
    print("This matches what Web Bluetooth / bleak forward after decoding notify bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
