"""
Nuke Console — example app that integrates BioAuth via the Python SDK.

This is a tiny FastAPI server representing "your application". When the user
tries to launch nukes, the server calls BioAuth to verify their identity
before allowing it.

Run:
    pip install fastapi uvicorn
    uvicorn demo.server:app --port 9000
"""

import sys
from pathlib import Path

# Make the SDK importable without installing it as a package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "python"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from bioauth.client import BioAuthClient

app = FastAPI(title="Nuke Console")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

bioauth = BioAuthClient(base_url="http://localhost:8000", api_key="dev-api-key-001")

NUKE_CODES = ["ALPHA-7749", "BRAVO-0158", "CHARLIE-3312"]


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.post("/launch")
async def launch():
    """User wants to launch — ask BioAuth if they're allowed."""
    try:
        result = bioauth.authorize(user_id="operator", action="launch_nukes", risk_level="critical")
    except Exception:
        return {
            "authorized": False,
            "codes": None,
            "bioauth": {
                "decision": "deny",
                "confidence": 0.0,
                "reasons": ["BIOAUTH_UNREACHABLE"],
            },
        }

    if result["decision"] == "allow":
        return {
            "authorized": True,
            "codes": NUKE_CODES,
            "bioauth": result,
        }
    return {
        "authorized": False,
        "codes": None,
        "bioauth": result,
    }
