from abc import ABC, abstractmethod

from backend.app.schemas.auth import VerificationPayload
from backend.app.schemas.enrollment import EnrollmentPayload


class TransportBase(ABC):
    """Abstract transport layer for communicating with the edge device (Pi)."""

    @abstractmethod
    async def request_verification(self, user_id: str) -> VerificationPayload:
        """Ask the edge device to capture ECG and return a verification payload."""
        ...

    @abstractmethod
    async def request_enrollment(self, user_id: str) -> EnrollmentPayload:
        """Ask the edge device to capture ECG and return an enrollment payload."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the edge device is reachable."""
        ...
