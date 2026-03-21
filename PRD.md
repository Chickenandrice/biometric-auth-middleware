1. Objective
   Build a step-up authentication service that uses live ECG signals to approve or block sensitive actions.
   Applications call BioAuth before executing high-risk operations. The system verifies a real, present human and returns:
   allow
   deny
   step_up

2. Product Concept
   BioAuth is a drop-in authorization middleware, similar to DUO.
   Applications handle login normally
   For sensitive actions, they call BioAuth
   BioAuth performs ECG-based verification
   Returns a decision with confidence and reason codes
   Integration options
   Direct API call
   Lightweight Python SDK

3. Core System Design
   High-level architecture
   [Demo App / SDK] → [Auth Backend API] → [Transport Layer] → [Edge Verifier on Pi] → [ADS1115] → [AD8232 ECG]
   │ (Bluetooth or HTTP)
   │
   ├── [SQL DB: users, baselines, logs, policies]
   └── [Vector DB: ECG embeddings]

[Admin Dashboard] → [Auth Backend API]

4. Component Responsibilities
   A. Edge Verifier (Raspberry Pi)
   Owns hardware and on-device signal handling.
   Responsibilities
   Read ECG from AD8232 through ADS1115 over I2C
   Filter signal
   Detect R-peaks
   Compute BPM, HRV, signal quality
   Generate ECG embedding / feature vector
   Send enrollment or verification payload to backend
   Optionally keep local cache/logs for offline mode
   Output to backend
   embedding
   BPM
   HRV
   signal quality
   timestamp
   user_id / mode

B. Transport Layer
Lets backend talk to Pi using either:
Bluetooth
HTTP
This should be abstracted so the rest of the backend does not care which one is being used.
Why this is the right design
Bluetooth gives a local/offline demo story
HTTP is easier to debug and use as fallback
same auth logic works with both

C. Auth Backend (FastAPI)
Owns orchestration, policy, storage, and decisions.
Responsibilities
Expose POST /authorize
Expose enrollment endpoints
Request fresh verification from the Pi
Receive live embedding/features
Fetch enrolled template from vector DB
Compute similarity score
Compute anomaly score from baseline deviation
Apply allow/deny/step_up policy
Store logs and enrollment state
Serve dashboard and demo app data

D. Vector DB
Stores ECG template embeddings.
Stores
user_id
embedding vector
metadata
template version / timestamp
This becomes the enrollment backup and recovery layer if the Pi is replaced.

E. SQL / Relational DB
Stores non-vector application state.
Stores
users
enrollment status
baselines (BPM/HRV)
policies
audit logs
request history

F. Demo App Portal
Represents the relying application.
Responsibilities
Show sensitive actions such as:
approve transfer
delete user
export data
Call BioAuth before action execution
Display approved / blocked / pending result

G. Admin Dashboard
Represents the control plane.
Responsibilities
Show enrolled users and status
Trigger enroll / unenroll
Show auth logs
Show decision confidence
Show live ECG waveform or metrics
Show anomaly / duress indicator

H. Optional SDK
Thin client wrapper for developers.
Example:
from bioauth import authorize

result = authorize(
user_id="alice",
action="approve_transfer",
risk_level="critical"
)

Internally calls backend API.

5. Main Flows
   Enrollment flow
   Admin clicks Enroll User
   Dashboard calls backend
   Backend requests enrollment from Pi via Bluetooth or HTTP
   Pi captures ECG and computes embedding + baseline stats
   Pi sends data to backend
   Backend stores:
   embedding in vector DB
   baseline stats in SQL DB
   enrollment status = true
   Verification flow
   User triggers a sensitive action in demo app
   Demo app or SDK calls POST /authorize
   Backend requests live verification from Pi
   Pi captures ECG and sends embedding + features
   Backend:
   retrieves enrolled embedding
   computes identity similarity
   computes anomaly score
   applies policy logic
   Backend returns allow, deny, or step_up
   Demo app executes or blocks action
   Dashboard displays result and logs

6. Decision Logic
   Simple version
   Poor signal quality → step_up
   Low identity similarity → deny
   High anomaly score → deny
   Otherwise → allow
   Risk levels
   Low → no ECG required
   High → identity check
   Critical → identity + anomaly threshold

7. Offline / Fallback Approach
   Keep this lightweight.
   Bluetooth mode
   Pi can send data locally without Wi-Fi
   good for local/offline demo story
   HTTP mode
   fallback transport if Bluetooth is unstable
   easier debugging and integration
   Optional offline behavior
   Pi temporarily caches enrollment data / recent logs
   backend syncs when connection is restored
   For the hackathon, the smartest approach is:
   support both transport modes
   prefer whichever is more stable at demo time

8. Data and Security Model
   Stored
   ECG embeddings
   baseline stats (BPM, HRV)
   logs
   enrollment status
   policies
   Not stored by default
   raw ECG waveform long-term
   Security approach
   embeddings treated as sensitive biometric templates
   vector DB stores encrypted or protected templates if possible
   backend uses token-authenticated API
   dashboard and demo app never directly see raw templates

9. Tech Stack
   Edge / Raspberry Pi
   Python
   smbus2 — ADS1115 I2C communication
   numpy — numerical processing
   scipy — filtering / signal processing
   scikit-learn or lightweight PyTorch — embedding / scoring
   Bleak or PyBluez — Bluetooth transport
   optional FastAPI — HTTP fallback transport on Pi
   local SQLite or JSON cache if needed
   Backend
   FastAPI
   uvicorn
   pydantic
   numpy
   scikit-learn for cosine similarity / simple scoring
   SQLAlchemy or SQLModel
   SQLite for hackathon DB
   Qdrant or Chroma for vector DB
   Frontend
   HTML
   CSS
   JavaScript
   Chart.js for waveform / metrics
   polling or websocket for live updates
   SDK
   Python
   requests

10. Recommended Implementation Strategy
    Phase 1 — Hardware and signal pipeline
    wire AD8232 + ADS1115 + Pi
    collect ECG samples
    bandpass filter
    detect R-peaks
    compute BPM and HRV
    verify clean live waveform
    Phase 2 — Embedding and scoring
    convert ECG window into feature vector / embedding
    store enrollment template
    compare live sample to template using cosine similarity
    compute anomaly score from BPM/HRV deviation
    Phase 3 — Backend and storage
    build FastAPI backend
    add /authorize, enrollment, logs, users
    integrate SQL DB and vector DB
    Phase 4 — Transport layer
    implement transport abstraction
    add Bluetooth transport
    add HTTP fallback transport
    Phase 5 — Frontend
    build demo app portal
    build admin dashboard
    display live state, decisions, and logs
    Phase 6 — SDK and polish
    simple Python wrapper
    reason codes
    enrollment status view
    clean demo scenarios

11. Team Split (4 People)
12. Hardware + signal pipeline
    Owns:
    sensor wiring
    ADS1115 reading
    ECG acquisition
    filtering
    R-peak detection
    BPM / HRV
    Suggested files:
    edge/acquisition/\*
    edge/processing/filters.py
    edge/processing/peaks.py
    edge/processing/features.py
13. Embedding + scoring
    Owns:
    enrollment template creation
    embedding generation
    similarity score
    anomaly logic
    thresholds
    Suggested files:
    edge/processing/embedding.py
    backend/app/services/scoring_service.py
    backend/app/utils/similarity.py
    backend/app/utils/thresholds.py
14. Backend + transport + storage
    Owns:
    FastAPI backend
    auth endpoints
    enrollment endpoints
    Bluetooth / HTTP transport adapters
    SQL DB + vector DB integration
    logs
    Suggested files:
    backend/app/api/_
    backend/app/services/auth_service.py
    backend/app/services/transport/_
    backend/app/services/vector_store_service.py
    backend/app/db/\*
15. Frontend + SDK
    Owns:
    admin dashboard
    demo app portal
    user enrollment UI
    Python SDK wrapper
    Suggested files:
    frontend/dashboard/_
    frontend/demo_app/_
    sdk/python/\*

16. Recommended File Structure
    bioauth/
    ├── README.md
    ├── requirements.txt
    ├── .env
    ├── docker-compose.yml
    │
    ├── backend/
    │ ├── app/
    │ │ ├── main.py
    │ │ ├── config.py
    │ │ ├── api/
    │ │ │ ├── authorize.py
    │ │ │ ├── enroll.py
    │ │ │ ├── users.py
    │ │ │ ├── logs.py
    │ │ │ └── status.py
    │ │ ├── services/
    │ │ │ ├── auth_service.py
    │ │ │ ├── enrollment_service.py
    │ │ │ ├── scoring_service.py
    │ │ │ ├── vector_store_service.py
    │ │ │ └── transport/
    │ │ │ ├── base.py
    │ │ │ ├── bluetooth_transport.py
    │ │ │ └── http_transport.py
    │ │ ├── db/
    │ │ │ ├── models.py
    │ │ │ ├── session.py
    │ │ │ └── crud.py
    │ │ ├── schemas/
    │ │ │ ├── auth.py
    │ │ │ ├── enrollment.py
    │ │ │ ├── user.py
    │ │ │ └── log.py
    │ │ └── utils/
    │ │ ├── similarity.py
    │ │ ├── thresholds.py
    │ │ └── security.py
    │ └── tests/
    │
    ├── edge/
    │ ├── main.py
    │ ├── config.py
    │ ├── acquisition/
    │ │ ├── ads1115_reader.py
    │ │ ├── ecg_stream.py
    │ │ └── sensor_check.py
    │ ├── processing/
    │ │ ├── filters.py
    │ │ ├── peaks.py
    │ │ ├── features.py
    │ │ ├── quality.py
    │ │ └── embedding.py
    │ ├── transport/
    │ │ ├── bluetooth_sender.py
    │ │ ├── bluetooth_protocol.py
    │ │ ├── pairing.py
    │ │ └── http_server.py
    │ ├── storage/
    │ │ ├── local_cache.py
    │ │ └── local_logs.py
    │ └── tests/
    │
    ├── frontend/
    │ ├── dashboard/
    │ │ ├── index.html
    │ │ ├── dashboard.js
    │ │ ├── charts.js
    │ │ └── styles.css
    │ └── demo_app/
    │ ├── index.html
    │ ├── app.js
    │ └── styles.css
    │
    ├── sdk/
    │ └── python/
    │ ├── bioauth/
    │ │ ├── **init**.py
    │ │ └── client.py
    │ └── setup.py
    │
    └── scripts/
    ├── seed_users.py
    ├── simulate_auth.py
    └── demo_reset.py

17. Minimal Payload Shape
    Verify payload from Pi to backend
    {
    "user_id": "alice",
    "mode": "verify",
    "embedding": [0.12, -0.88, 0.41],
    "bpm": 79,
    "hrv": 38,
    "signal_quality": 0.91,
    "timestamp": "2026-03-21T18:30:00Z"
    }

Backend response to app
{
"decision": "allow",
"confidence": 0.91,
"reason_codes": ["IDENTITY_MATCH"]
}

14. Demo Plan
    Scenario 1 — Normal approval
    stable ECG
    high similarity
    low anomaly
    action allowed
    Scenario 2 — Denial
    lower similarity or elevated anomaly
    action blocked
    Scenario 3 — Transport fallback
    Bluetooth unavailable
    HTTP transport used instead
    system still works
    That last scenario is actually a strong demo point because it shows resilience.

15. Success Criteria
    Enrollment works from dashboard
    Sensitive action triggers /authorize
    Pi captures ECG and returns live data
    Backend matches against stored embedding
    Clear allow/deny result appears in demo app
    Dashboard shows waveform, status, and logs
    Bluetooth and HTTP are both supported at the transport layer

16. Final Positioning
    BioAuth Gateway is a drop-in step-up authentication service with an optional SDK. A Raspberry Pi captures ECG, generates embeddings on-device, sends them to a backend over Bluetooth or HTTP, and the backend performs identity matching, anomaly scoring, policy checks, and logging before approving high-risk actions.
    If you want, I can next turn this into a clean slide-ready architecture diagram and a 24-hour team task breakdown.
