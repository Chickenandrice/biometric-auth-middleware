"""Tests for /users API endpoints."""

import pytest
from backend.tests.conftest import API_KEY_HEADER


class TestUsersAPI:
    @pytest.mark.asyncio
    async def test_create_user(self, client):
        resp = await client.post(
            "/users",
            json={"user_id": "alice", "display_name": "Alice Chen"},
            headers=API_KEY_HEADER,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "alice"
        assert data["display_name"] == "Alice Chen"
        assert data["enrolled"] is False

    @pytest.mark.asyncio
    async def test_create_duplicate_user(self, client):
        await client.post("/users", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        resp = await client.post("/users", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_users_empty(self, client):
        resp = await client.get("/users", headers=API_KEY_HEADER)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_users(self, client):
        await client.post("/users", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await client.post("/users", json={"user_id": "bob"}, headers=API_KEY_HEADER)
        resp = await client.get("/users", headers=API_KEY_HEADER)
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_user(self, client):
        await client.post("/users", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        resp = await client.get("/users/alice", headers=API_KEY_HEADER)
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client):
        resp = await client.get("/users/ghost", headers=API_KEY_HEADER)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_api_key_rejected(self, client):
        resp = await client.get("/users")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_bad_api_key_rejected(self, client):
        resp = await client.get("/users", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_user_missing_user_id(self, client):
        resp = await client.post("/users", json={}, headers=API_KEY_HEADER)
        assert resp.status_code == 422
