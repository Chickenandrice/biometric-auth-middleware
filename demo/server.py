"""
Nuke Console — example app that integrates BioAuth via the Python SDK.

This is a tiny FastAPI server representing "your application". When the user
tries to launch nukes, the server calls BioAuth to verify their identity
before allowing it.

Run:
    pip install fastapi uvicorn
    uvicorn demo.server:app --port 9000
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Make the SDK importable without installing it as a package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "python"))

import httpx
import jwt as pyjwt
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from bioauth.client import BioAuthClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DASHBOARD_DIR = _REPO_ROOT / "frontend" / "dashboard"

# Same gateway the dashboard uses — override for remote gateways
GATEWAY_URL = os.getenv("BIOAUTH_GATEWAY_URL", "http://localhost:8000").rstrip("/")
GATEWAY_API_KEY = os.getenv("BIOAUTH_GATEWAY_API_KEY", "dev-api-key-001")

app = FastAPI(title="Nuke Console")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

bioauth = BioAuthClient(base_url=GATEWAY_URL, api_key=GATEWAY_API_KEY)

# Auth0 config
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "YOUR_AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ALGORITHMS = ["RS256"]

_jwks_cache = None

async def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
            _jwks_cache = resp.json()
    return _jwks_cache

async def verify_auth0_token(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    jwks = await get_jwks()
    try:
        unverified = pyjwt.get_unverified_header(token)
        key = None
        for k in jwks.get("keys", []):
            if k["kid"] == unverified.get("kid"):
                key = pyjwt.algorithms.RSAAlgorithm.from_jwk(k)
                break
        if key is None:
            raise HTTPException(status_code=401, detail="Invalid token key")
        payload = pyjwt.decode(
            token, key, algorithms=AUTH0_ALGORITHMS,
            issuer=f"https://{AUTH0_DOMAIN}/",
            options={"verify_aud": False},
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

NUKE_CODES = ["ALPHA-7749", "BRAVO-0158", "CHARLIE-3312"]


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/landing-page")
async def landing_page():
    return FileResponse(Path(__file__).parent / "landing.html")


def _auth0_configured() -> bool:
    d = os.getenv("AUTH0_DOMAIN", "")
    c = os.getenv("AUTH0_CLIENT_ID", "")
    return bool(d and c and not d.startswith("YOUR_") and not c.startswith("YOUR_"))


@app.get("/auth-config")
async def auth_config():
    """SPA reads domain/clientId; redirectUri overrides browser origin when set (must match Auth0 exactly)."""
    redirect = os.getenv("AUTH0_REDIRECT_URI", "").strip() or None
    return {
        "domain": AUTH0_DOMAIN,
        "clientId": os.getenv("AUTH0_CLIENT_ID", "YOUR_AUTH0_CLIENT_ID"),
        "configured": _auth0_configured(),
        "redirectUri": redirect,
    }


@app.get("/demo-config")
async def demo_config():
    """Browser writes these to dashboard localStorage (same origin as this demo on :9000)."""
    return {"gatewayUrl": GATEWAY_URL, "apiKey": GATEWAY_API_KEY}


@app.post("/launch")
async def launch(request: Request):
    """User wants to launch — ask BioAuth if they're allowed."""
    user_info = await verify_auth0_token(request)
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


if _DASHBOARD_DIR.is_dir():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
        name="dashboard",
    )
