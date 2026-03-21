"""Tests for POST /relay/enrollment and POST /relay/authorize (BLE-relayed JSON)."""

import pytest

from backend.tests.conftest import API_KEY_HEADER, ENROLLED_EMBEDDING


def _enrollment_json(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "mode": "enroll",
        "embedding": ENROLLED_EMBEDDING,
        "bpm": 74.0,
        "hrv": 40.0,
        "signal_quality": 0.95,
        "timestamp": "2026-03-21T18:30:00Z",
    }


def _verification_json(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "mode": "verify",
        "embedding": ENROLLED_EMBEDDING,
        "bpm": 74.0,
        "hrv": 40.0,
        "signal_quality": 0.95,
        "timestamp": "2026-03-21T18:30:00Z",
    }


class TestRelayAPI:
    @pytest.mark.asyncio
    async def test_relay_enrollment_ok(self, client):
        uid = "relay_user_enroll"
        resp = await client.post(
            "/relay/enrollment",
            json=_enrollment_json(uid),
            headers=API_KEY_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrolled"] is True
        assert data["user_id"] == uid

    @pytest.mark.asyncio
    async def test_relay_enrollment_requires_api_key(self, client):
        resp = await client.post(
            "/relay/enrollment",
            json=_enrollment_json("x"),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_relay_authorize_ok_after_enroll(self, client):
        uid = "relay_user_auth"
        await client.post(
            "/relay/enrollment",
            json=_enrollment_json(uid),
            headers=API_KEY_HEADER,
        )
        resp = await client.post(
            "/relay/authorize",
            json={
                "user_id": uid,
                "action": "transfer",
                "risk_level": "high",
                "verification": _verification_json(uid),
            },
            headers=API_KEY_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "allow"
        assert "IDENTITY_MATCH" in data["reason_codes"]

    @pytest.mark.asyncio
    async def test_relay_authorize_user_id_mismatch_400(self, client):
        uid = "relay_user_mismatch"
        await client.post(
            "/relay/enrollment",
            json=_enrollment_json(uid),
            headers=API_KEY_HEADER,
        )
        resp = await client.post(
            "/relay/authorize",
            json={
                "user_id": uid,
                "action": "transfer",
                "risk_level": "high",
                "verification": _verification_json("other_user"),
            },
            headers=API_KEY_HEADER,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_relay_authorize_requires_api_key(self, client):
        resp = await client.post(
            "/relay/authorize",
            json={
                "user_id": "a",
                "action": "t",
                "verification": _verification_json("a"),
            },
        )
        assert resp.status_code == 401
