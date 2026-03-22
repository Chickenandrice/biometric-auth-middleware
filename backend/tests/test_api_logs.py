"""Tests for /logs API endpoint."""

import pytest
from backend.tests.conftest import API_KEY_HEADER


class TestLogsAPI:
    @pytest.mark.asyncio
    async def test_logs_empty(self, client):
        resp = await client.get("/logs", headers=API_KEY_HEADER)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_logs_populated_after_authorize(self, client):
        # Enroll and authorize to generate a log entry
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        resp = await client.get("/logs", headers=API_KEY_HEADER)
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["user_id"] == "alice"
        assert logs[0]["decision"] in ("allow", "deny", "step_up")
        assert logs[0]["action"] == "transfer"

    @pytest.mark.asyncio
    async def test_logs_filter_by_user(self, client):
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await client.post("/enroll", json={"user_id": "bob"}, headers=API_KEY_HEADER)
        await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        await client.post(
            "/authorize",
            json={"user_id": "bob", "action": "delete", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        resp = await client.get("/logs?user_id=alice", headers=API_KEY_HEADER)
        logs = resp.json()
        assert all(log["user_id"] == "alice" for log in logs)

    @pytest.mark.asyncio
    async def test_logs_pagination(self, client):
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        for _ in range(5):
            await client.post(
                "/authorize",
                json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
                headers=API_KEY_HEADER,
            )
        resp = await client.get("/logs?limit=2&offset=0", headers=API_KEY_HEADER)
        assert len(resp.json()) == 2
        resp2 = await client.get("/logs?limit=2&offset=2", headers=API_KEY_HEADER)
        assert len(resp2.json()) == 2

    @pytest.mark.asyncio
    async def test_logs_contains_scores(self, client):
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        resp = await client.get("/logs", headers=API_KEY_HEADER)
        log = resp.json()[0]
        assert "similarity_score" in log
        assert "signal_quality" in log
        assert "bpm" in log
        assert "reason_codes" in log

    @pytest.mark.asyncio
    async def test_logs_not_enrolled_denial_recorded(self, client):
        await client.post(
            "/authorize",
            json={"user_id": "ghost", "action": "launch_nukes", "risk_level": "critical"},
            headers=API_KEY_HEADER,
        )
        resp = await client.get("/logs", headers=API_KEY_HEADER)
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["user_id"] == "ghost"
        assert logs[0]["decision"] == "deny"
        assert "NOT_ENROLLED" in (logs[0].get("reason_codes") or [])

    @pytest.mark.asyncio
    async def test_logs_requires_api_key(self, client):
        resp = await client.get("/logs")
        assert resp.status_code == 401
