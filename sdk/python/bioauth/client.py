import requests


class BioAuthClient:
    """Lightweight Python SDK for the BioAuth Gateway API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "dev-api-key-001",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key

    # ── Authorization ──

    def authorize(self, user_id: str, action: str, risk_level: str = "high") -> dict:
        """Request biometric authorization for a sensitive action."""
        resp = self._session.post(
            f"{self.base_url}/authorize",
            json={"user_id": user_id, "action": action, "risk_level": risk_level},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Enrollment ──

    def enroll(self, user_id: str) -> dict:
        resp = self._session.post(
            f"{self.base_url}/enroll",
            json={"user_id": user_id},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def unenroll(self, user_id: str) -> dict:
        resp = self._session.post(
            f"{self.base_url}/unenroll",
            json={"user_id": user_id},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Users ──

    def list_users(self) -> list[dict]:
        resp = self._session.get(f"{self.base_url}/users", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def create_user(self, user_id: str, display_name: str | None = None) -> dict:
        resp = self._session.post(
            f"{self.base_url}/users",
            json={"user_id": user_id, "display_name": display_name},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_user(self, user_id: str) -> dict:
        resp = self._session.get(
            f"{self.base_url}/users/{user_id}", timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    # ── Logs ──

    def list_logs(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if user_id:
            params["user_id"] = user_id
        resp = self._session.get(
            f"{self.base_url}/logs", params=params, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    # ── Status ──

    def health(self) -> dict:
        resp = self._session.get(f"{self.base_url}/health", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        resp = self._session.get(f"{self.base_url}/status", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


# ── Convenience function ──

_default_client: BioAuthClient | None = None


def authorize(user_id: str, action: str, risk_level: str = "high", **kwargs) -> dict:
    """Quick one-liner authorization call (as shown in PRD).

    Usage:
        from bioauth import authorize
        result = authorize(user_id="alice", action="approve_transfer", risk_level="critical")
    """
    global _default_client
    if _default_client is None:
        _default_client = BioAuthClient(**kwargs)
    return _default_client.authorize(user_id, action, risk_level)
