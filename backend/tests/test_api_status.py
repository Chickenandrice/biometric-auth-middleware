"""Tests for /health and /status endpoints."""

import pytest
from backend.tests.conftest import API_KEY_HEADER


class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data


class TestStatusAPI:
    @pytest.mark.asyncio
    async def test_status_requires_api_key(self, client):
        resp = await client.get("/status")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_status_returns_transport_info(self, client):
        resp = await client.get("/status", headers=API_KEY_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert "transport_mode" in data
        assert "edge_connected" in data
        assert data["edge_connected"] is True  # mock transport returns True

    @pytest.mark.asyncio
    async def test_status_edge_disconnected(self, client_with_transport):
        ac = await client_with_transport(should_fail=True)
        resp = await ac.get("/status", headers=API_KEY_HEADER)
        data = resp.json()
        assert data["edge_connected"] is False
        await ac.aclose()
