# BioAuth Gateway — Backend API Contract

Base URL: `http://localhost:8000`

## Authentication

All endpoints (except `GET /health`) require an API key via the `X-API-Key` header.

```
X-API-Key: dev-api-key-001
```

Requests without a valid key receive `401 Unauthorized`:

```json
{ "detail": "Invalid or missing API key" }
```

---

## Endpoints

### POST /authorize

Authorize a sensitive action via biometric ECG verification. This is the primary endpoint that frontend apps and the SDK call before allowing high-risk operations.

**Request:**

```json
{
  "user_id": "alice",
  "action": "approve_transfer",
  "risk_level": "high"
}
```

| Field        | Type   | Required | Default  | Description                              |
|-------------|--------|----------|----------|------------------------------------------|
| `user_id`   | string | yes      |          | The user attempting the action            |
| `action`    | string | yes      |          | The sensitive action being attempted      |
| `risk_level`| string | no       | `"high"` | `"low"`, `"high"`, or `"critical"`       |

**Response:**

```json
{
  "decision": "allow",
  "confidence": 0.91,
  "reason_codes": ["IDENTITY_MATCH"]
}
```

| Field          | Type     | Description                                      |
|---------------|----------|--------------------------------------------------|
| `decision`    | string   | `"allow"`, `"deny"`, or `"step_up"`              |
| `confidence`  | float    | Confidence score (0.0–1.0)                        |
| `reason_codes`| string[] | Machine-readable reasons for the decision         |

**Decision logic by risk level:**

| Risk Level | Behavior                                                  |
|-----------|-----------------------------------------------------------|
| `low`     | Always returns `allow` — no biometric check               |
| `high`    | Identity similarity must exceed threshold (default 0.75)  |
| `critical`| Identity check + anomaly detection (BPM/HRV deviation)   |

**Reason codes:**

| Code                | Meaning                                          |
|--------------------|--------------------------------------------------|
| `LOW_RISK_BYPASS`  | Low-risk action, no biometric needed              |
| `IDENTITY_MATCH`   | ECG identity verified successfully                |
| `IDENTITY_MISMATCH`| Live ECG did not match enrolled template          |
| `ANOMALY_DETECTED` | BPM/HRV deviation suggests stress or duress      |
| `POOR_SIGNAL`      | ECG signal quality too low — retry recommended    |
| `NOT_ENROLLED`     | User has not completed enrollment                 |
| `NO_TEMPLATE`      | Enrolled user but embedding missing from store    |
| `TRANSPORT_ERROR`  | Could not reach the edge device (Pi)              |

---

### POST /enroll

Enroll a user by capturing their ECG baseline from the edge device.

**Request:**

```json
{
  "user_id": "alice"
}
```

**Response (success):**

```json
{
  "user_id": "alice",
  "enrolled": true,
  "message": "Enrollment successful."
}
```

**Response (poor signal):**

```json
{
  "user_id": "alice",
  "enrolled": false,
  "message": "Signal quality too low for enrollment. Please try again."
}
```

| Field      | Type   | Description                           |
|-----------|--------|---------------------------------------|
| `user_id` | string | The user being enrolled               |
| `enrolled`| bool   | Whether enrollment succeeded          |
| `message` | string | Human-readable status message         |

If the user doesn't exist yet, they are created automatically during enrollment.

---

### POST /unenroll

Remove a user's biometric enrollment. Deletes their ECG template from the vector store.

**Request:**

```json
{
  "user_id": "alice"
}
```

**Response:**

```json
{
  "user_id": "alice",
  "enrolled": false,
  "message": "User unenrolled."
}
```

---

### GET /users

List all registered users.

**Response:**

```json
[
  {
    "user_id": "alice",
    "display_name": "Alice Chen",
    "enrolled": true,
    "enrolled_at": "2026-03-21T18:30:00",
    "created_at": "2026-03-21T18:00:00"
  }
]
```

---

### POST /users

Create a new user.

**Request:**

```json
{
  "user_id": "alice",
  "display_name": "Alice Chen"
}
```

| Field          | Type        | Required | Description             |
|---------------|-------------|----------|-------------------------|
| `user_id`     | string      | yes      | Unique user identifier  |
| `display_name`| string/null | no       | Display name            |

**Response:** `201 Created` with the user object (same shape as GET).

**Errors:**

- `409 Conflict` — `{ "detail": "User already exists" }`

---

### GET /users/{user_id}

Get a single user by ID.

**Response:** User object (same shape as list items).

**Errors:**

- `404 Not Found` — `{ "detail": "User not found" }`

---

### GET /logs

List audit logs for authorization decisions.

**Query parameters:**

| Param    | Type        | Default | Description                      |
|---------|-------------|---------|----------------------------------|
| `user_id`| string/null| `null`  | Filter logs by user              |
| `limit` | int         | `50`    | Max results (1–500)              |
| `offset`| int         | `0`     | Pagination offset                |

**Response:**

```json
[
  {
    "id": 1,
    "user_id": "alice",
    "action": "approve_transfer",
    "decision": "allow",
    "confidence": 0.91,
    "reason_codes": ["IDENTITY_MATCH"],
    "similarity_score": 0.91,
    "anomaly_score": 0.3,
    "signal_quality": 0.95,
    "bpm": 74.0,
    "hrv": 40.0,
    "transport_mode": "http",
    "timestamp": "2026-03-21T18:30:00"
  }
]
```

---

### GET /health

Public health check (no API key required).

**Response:**

```json
{
  "status": "ok",
  "service": "BioAuth Gateway"
}
```

---

### GET /status

System status including edge device connectivity.

**Response:**

```json
{
  "service": "BioAuth Gateway",
  "transport_mode": "http",
  "edge_connected": true
}
```

---

## Error Responses

All errors follow FastAPI's standard format:

```json
{
  "detail": "Error message here"
}
```

| Status | Meaning                          |
|--------|----------------------------------|
| 401    | Missing or invalid API key       |
| 404    | Resource not found               |
| 409    | Conflict (e.g. duplicate user)   |
| 422    | Validation error (bad request body) |

Validation errors include field-level detail:

```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## Interactive Docs

FastAPI auto-generates interactive API documentation:

- **Swagger UI:** `GET /docs`
- **ReDoc:** `GET /redoc`
- **OpenAPI JSON:** `GET /openapi.json`

---

## Frontend Integration Patterns

### Demo App (sensitive action flow)

```javascript
// Before executing a sensitive action:
const response = await fetch("/authorize", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
  },
  body: JSON.stringify({
    user_id: currentUser,
    action: "approve_transfer",
    risk_level: "critical"
  })
});

const { decision, confidence, reason_codes } = await response.json();

if (decision === "allow") {
  executeTransfer();
} else if (decision === "step_up") {
  showRetryPrompt(reason_codes);
} else {
  showDenied(reason_codes);
}
```

### Admin Dashboard (polling for live state)

```javascript
// Fetch enrolled users
const users = await fetch("/users", { headers: { "X-API-Key": API_KEY } })
  .then(r => r.json());

// Fetch recent auth decisions
const logs = await fetch("/logs?limit=20", { headers: { "X-API-Key": API_KEY } })
  .then(r => r.json());

// Check edge device connectivity
const status = await fetch("/status", { headers: { "X-API-Key": API_KEY } })
  .then(r => r.json());
```

### Enrollment (triggered from dashboard)

```javascript
const result = await fetch("/enroll", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
  },
  body: JSON.stringify({ user_id: "alice" })
});

const { enrolled, message } = await result.json();
```
