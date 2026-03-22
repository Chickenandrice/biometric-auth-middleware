"""Simulated transport that returns fake ECG data — no Pi needed."""

import numpy as np
from datetime import datetime, timezone

from backend.app.schemas.auth import VerificationPayload
from backend.app.schemas.enrollment import EnrollmentPayload
from backend.app.services.transport.base import TransportBase

# Fixed seed so enrollment and verification embeddings are related
_rng = np.random.default_rng(42)
_base_embedding = _rng.standard_normal(64)
_base_embedding = (_base_embedding / np.linalg.norm(_base_embedding)).tolist()


class SimulatedTransport(TransportBase):
    """Returns realistic fake ECG payloads for demo without hardware."""

    async def request_verification(self, user_id: str) -> VerificationPayload:
        # Add slight noise to the base embedding (simulates real recapture)
        rng = np.random.default_rng()
        base = np.array(_base_embedding)
        noisy = base + rng.standard_normal(64) * 0.04
        noisy = (noisy / np.linalg.norm(noisy)).tolist()

        return VerificationPayload(
            user_id=user_id,
            mode="verify",
            embedding=noisy,
            bpm=72 + rng.standard_normal() * 3,
            hrv=42 + rng.standard_normal() * 4,
            signal_quality=0.92 + rng.random() * 0.07,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def request_enrollment(self, user_id: str) -> EnrollmentPayload:
        return EnrollmentPayload(
            user_id=user_id,
            mode="enroll",
            embedding=_base_embedding,
            bpm=72.0,
            hrv=42.0,
            signal_quality=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def health_check(self) -> bool:
        return True
