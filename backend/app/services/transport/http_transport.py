import httpx

from backend.app.config import settings
from backend.app.schemas.auth import VerificationPayload
from backend.app.schemas.enrollment import EnrollmentPayload
from backend.app.services.transport.base import TransportBase


class HttpTransport(TransportBase):
    """Communicates with the edge device over HTTP."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.edge_http_url).rstrip("/")

    async def request_verification(self, user_id: str) -> VerificationPayload:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/capture",
                json={"user_id": user_id, "mode": "verify"},
            )
            resp.raise_for_status()
            return VerificationPayload(**resp.json())

    async def request_enrollment(self, user_id: str) -> EnrollmentPayload:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/capture",
                json={"user_id": user_id, "mode": "enroll"},
            )
            resp.raise_for_status()
            return EnrollmentPayload(**resp.json())

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
