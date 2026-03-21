from pydantic import BaseModel


class EnrollRequest(BaseModel):
    user_id: str


class EnrollmentPayload(BaseModel):
    """Payload received from the edge device during enrollment."""
    user_id: str
    mode: str = "enroll"
    embedding: list[float]
    bpm: float
    hrv: float
    signal_quality: float
    timestamp: str


class EnrollResponse(BaseModel):
    user_id: str
    enrolled: bool
    message: str
