"""Tests for /enroll and /unenroll API endpoints."""

import pytest
from backend.tests.conftest import API_KEY_HEADER


class TestEnrollAPI:
    @pytest.mark.asyncio
    async def test_enroll_new_user(self, client):
        resp = await client.post(
            "/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrolled"] is True
        assert data["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_enroll_creates_user_if_needed(self, client):
        await client.post("/enroll", json={"user_id": "newuser"}, headers=API_KEY_HEADER)
        resp = await client.get("/users/newuser", headers=API_KEY_HEADER)
        assert resp.status_code == 200
        assert resp.json()["enrolled"] is True

    @pytest.mark.asyncio
    async def test_enroll_poor_signal_rejected(self, client_with_transport):
        ac = await client_with_transport(signal_quality=0.2)
        resp = await ac.post(
            "/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["enrolled"] is False
        assert "quality" in data["message"].lower()
        await ac.aclose()

    @pytest.mark.asyncio
    async def test_unenroll_user(self, client):
        # Enroll first
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        # Then unenroll
        resp = await client.post(
            "/unenroll", json={"user_id": "alice"}, headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["enrolled"] is False
        # Verify via /users
        user_resp = await client.get("/users/alice", headers=API_KEY_HEADER)
        assert user_resp.json()["enrolled"] is False

    @pytest.mark.asyncio
    async def test_enroll_requires_api_key(self, client):
        resp = await client.post("/enroll", json={"user_id": "alice"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_enroll_missing_user_id(self, client):
        resp = await client.post("/enroll", json={}, headers=API_KEY_HEADER)
        assert resp.status_code == 422
