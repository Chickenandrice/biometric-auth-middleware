# BioAuth — Biometric Step-Up Authentication Middleware

Drop-in authorization middleware that uses live ECG signals to approve or block sensitive actions. Applications call BioAuth before executing high-risk operations — it verifies a real, present human and returns `allow`, `deny`, or `step_up`.

```
[App / SDK] → [Auth Backend] → [Transport Layer] → [Edge Verifier (Pi)] → [AD8232 ECG]
                  │
                  ├── SQL DB (users, baselines, logs, policies)
                  └── Vector DB (ECG embeddings)
```

## Quick start

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run backend in simulation mode (no hardware needed)
BIOAUTH_TRANSPORT_MODE=simulate uvicorn backend.app.main:app --reload --port 8000

# 3. Run the demo app (its server calls BioAuth via the Python SDK)
uvicorn demo.server:app --port 9000
# Open http://localhost:9000 — click Authenticate to test the full flow

# 4. Open the admin dashboard (optional, static HTML)
open frontend/dashboard/index.html
```

Simulation mode auto-enrolls an "operator" user on startup so the demo works out of the box. Without it, the backend expects a real Raspberry Pi running the edge verifier:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── api/            Route handlers
│   │   ├── db/             Models, CRUD, session
│   │   ├── schemas/        Pydantic request/response models
│   │   ├── services/       Auth engine, enrollment, scoring, transport, vector store
│   │   └── utils/          API key security
├── demo/                   Demo app (SDK-integrated, has its own server)
├── frontend/
│   └── dashboard/          Admin panel
├── sdk/
│   └── python/             Python SDK
└── scripts/                Seed data, simulate auth, reset
```

## How it works

1. App calls `POST /authorize` with a `user_id`, `action`, and `risk_level`
2. Backend checks enrollment, captures ECG via transport layer, then runs:
   - **Signal quality gate** — rejects noisy readings
   - **Identity matching** — cosine similarity against enrolled ECG embedding
   - **Anomaly detection** — z-score on BPM/HRV vs. stored baseline
3. Decision engine applies policy based on risk level:
   - `low` → bypass (no biometric needed)
   - `high` → identity check only
   - `critical` → identity + anomaly check
4. Returns `allow` / `deny` / `step_up` with confidence score and reason codes

## Transport modes

| Mode        | Env var                            | Description                |
| ----------- | ---------------------------------- | -------------------------- |
| `simulate`  | `BIOAUTH_TRANSPORT_MODE=simulate`  | Fake ECG data, no hardware |
| `http`      | `BIOAUTH_TRANSPORT_MODE=http`      | Pi reachable over HTTP     |
| `bluetooth` | `BIOAUTH_TRANSPORT_MODE=bluetooth` | Pi reachable over BLE      |

## API overview

All endpoints require `X-API-Key` header (default: `dev-api-key-001`).

| Method | Endpoint            | Description                 |
| ------ | ------------------- | --------------------------- |
| POST   | `/authorize`        | Run biometric authorization |
| POST   | `/enroll`           | Enroll a user via transport |
| POST   | `/unenroll`         | Remove enrollment           |
| GET    | `/users`            | List users                  |
| POST   | `/users`            | Create user                 |
| GET    | `/logs`             | Audit log                   |
| GET    | `/health`           | Health check                |
| POST   | `/relay/enrollment` | BLE relay enrollment        |
| POST   | `/relay/authorize`  | BLE relay authorization     |

Interactive docs available at `http://localhost:8000/docs` when the backend is running.

## Tests

```bash
source .venv/bin/activate
pytest backend/tests/ -v
```

## SDK usage

```python
from bioauth.client import BioAuthClient

client = BioAuthClient(base_url="http://localhost:8000", api_key="dev-api-key-001")
result = client.authorize(user_id="operator", action="launch", risk_level="critical")
print(result["decision"])  # "allow" | "deny" | "step_up"
```

## Configuration

All settings are configurable via environment variables with `BIOAUTH_` prefix or a `.env` file. See [`backend/app/config.py`](backend/app/config.py) for all options.
