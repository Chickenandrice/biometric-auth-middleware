from pydantic import BaseModel
from datetime import datetime


class AuditLogOut(BaseModel):
    id: int
    user_id: str
    action: str | None
    decision: str
    confidence: float | None
    reason_codes: list[str] | None
    similarity_score: float | None
    anomaly_score: float | None
    signal_quality: float | None
    bpm: float | None
    hrv: float | None
    transport_mode: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}
