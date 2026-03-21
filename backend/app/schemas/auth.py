from pydantic import BaseModel


class AuthorizeRequest(BaseModel):
    user_id: str
    action: str
    risk_level: str = "high"  # low, high, critical


class AuthorizeResponse(BaseModel):
    decision: str  # allow, deny, step_up
    confidence: float
    reason_codes: list[str]


class VerificationPayload(BaseModel):
    """Payload received from the edge device after ECG capture."""
    user_id: str
    mode: str = "verify"
    embedding: list[float]
    bpm: float
    hrv: float
    signal_quality: float
    timestamp: str
