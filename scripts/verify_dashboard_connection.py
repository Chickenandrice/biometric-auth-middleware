#!/usr/bin/env python3
"""
Verify the BioAuth gateway is up and accepts the same calls the dashboard uses.

Usage (from repo root, with the API running on port 8000):

  python scripts/verify_dashboard_connection.py

Environment:
  BIOAUTH_URL     default http://127.0.0.1:8000
  BIOAUTH_API_KEY default dev-api-key-001
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("BIOAUTH_URL", "http://127.0.0.1:8000").rstrip("/")
    key = os.environ.get("BIOAUTH_API_KEY", "dev-api-key-001")

    print(f"URL: {base}")
    print("---")

    try:
        req = urllib.request.Request(f"{base}/health")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode()
        print("GET /health OK:", body.strip())
    except urllib.error.URLError as e:
        print("GET /health FAILED:", e, file=sys.stderr)
        print("Start the API:  python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000", file=sys.stderr)
        return 1

    headers = {"X-API-Key": key, "Accept": "application/json"}

    for path in ("/status", "/users", "/logs?limit=5"):
        try:
            req = urllib.request.Request(f"{base}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
            if path.startswith("/logs"):
                print(f"GET {path} OK: {len(data)} row(s)")
            elif path == "/users":
                print(f"GET {path} OK: {len(data)} user(s)")
            else:
                print(f"GET {path} OK:", json.dumps(data, indent=2)[:400])
        except urllib.error.HTTPError as e:
            print(f"GET {path} FAILED: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
            if e.code == 401:
                print("Check X-API-Key matches BIOAUTH_API_KEYS in backend config.", file=sys.stderr)
            return 1
        except urllib.error.URLError as e:
            print(f"GET {path} FAILED:", e, file=sys.stderr)
            return 1

    print("---")
    print("Dashboard: serve frontend/dashboard (e.g. python -m http.server 8765),")
    print("open http://localhost:8765/, uncheck mock, set API base to", base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
