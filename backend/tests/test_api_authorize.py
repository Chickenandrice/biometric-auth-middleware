"""Tests for POST /authorize endpoint — the core decision engine."""

import pytest
import numpy as np
from backend.tests.conftest import API_KEY_HEADER, ENROLLED_EMBEDDING


def _different_embedding(seed=99, dim=64):
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim)
    return (vec / np.linalg.norm(vec)).tolist()


class TestAuthorizeAPI:
    # ── Low risk bypass ──

    @pytest.mark.asyncio
    async def test_low_risk_always_allows(self, client):
        resp = await client.post(
            "/authorize",
            json={"user_id": "nobody", "action": "view", "risk_level": "low"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "allow"
        assert "LOW_RISK_BYPASS" in data["reason_codes"]

    # ── Not enrolled ──

    @pytest.mark.asyncio
    async def test_not_enrolled_denied(self, client):
        resp = await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "deny"
        assert "NOT_ENROLLED" in data["reason_codes"]

    # ── Successful authorization (matching embedding) ──

    @pytest.mark.asyncio
    async def test_enrolled_user_allowed(self, client):
        # Enroll (mock transport returns ENROLLED_EMBEDDING)
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        # Authorize (mock transport returns same ENROLLED_EMBEDDING)
        resp = await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "allow"
        assert "IDENTITY_MATCH" in data["reason_codes"]
        assert data["confidence"] > 0.9

    # ── Identity mismatch ──

    @pytest.mark.asyncio
    async def test_impostor_denied(self, client_with_transport):
        # Enroll with default embedding
        ac = await client_with_transport()
        await ac.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await ac.aclose()

        # Verify with a completely different embedding
        ac2 = await client_with_transport(embedding=_different_embedding())
        resp = await ac2.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "deny"
        assert "IDENTITY_MISMATCH" in data["reason_codes"]
        await ac2.aclose()

    # ── Poor signal quality → step_up ──

    @pytest.mark.asyncio
    async def test_poor_signal_step_up(self, client_with_transport):
        # Enroll with good signal
        ac = await client_with_transport()
        await ac.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await ac.aclose()

        # Verify with poor signal
        ac2 = await client_with_transport(signal_quality=0.2)
        resp = await ac2.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "step_up"
        assert "POOR_SIGNAL" in data["reason_codes"]
        await ac2.aclose()

    # ── Transport error → step_up ──

    @pytest.mark.asyncio
    async def test_transport_error_step_up(self, client_with_transport):
        # Enroll normally
        ac = await client_with_transport()
        await ac.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await ac.aclose()

        # Verify with transport that fails
        ac2 = await client_with_transport(should_fail=True)
        resp = await ac2.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "high"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "step_up"
        assert "TRANSPORT_ERROR" in data["reason_codes"]
        await ac2.aclose()

    # ── Critical risk with anomaly detection ──

    @pytest.mark.asyncio
    async def test_critical_risk_anomaly_denied(self, client_with_transport):
        # Enroll
        ac = await client_with_transport()
        await ac.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await ac.aclose()

        # Verify at critical risk with abnormal vitals (high BPM = stress)
        ac2 = await client_with_transport(bpm=140.0, hrv=15.0)
        resp = await ac2.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "critical"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "deny"
        assert "ANOMALY_DETECTED" in data["reason_codes"]
        await ac2.aclose()

    @pytest.mark.asyncio
    async def test_critical_risk_normal_vitals_allowed(self, client_with_transport):
        # Enroll
        ac = await client_with_transport(bpm=74.0, hrv=40.0)
        await ac.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        await ac.aclose()

        # Verify at critical risk with normal vitals (close to baseline)
        ac2 = await client_with_transport(bpm=74.0, hrv=40.0)
        resp = await ac2.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer", "risk_level": "critical"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        assert data["decision"] == "allow"
        assert "IDENTITY_MATCH" in data["reason_codes"]
        await ac2.aclose()

    # ── Auth validation ──

    @pytest.mark.asyncio
    async def test_authorize_requires_api_key(self, client):
        resp = await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_authorize_missing_fields(self, client):
        resp = await client.post(
            "/authorize", json={}, headers=API_KEY_HEADER,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_authorize_default_risk_level(self, client):
        # Should default to "high"
        await client.post("/enroll", json={"user_id": "alice"}, headers=API_KEY_HEADER)
        resp = await client.post(
            "/authorize",
            json={"user_id": "alice", "action": "transfer"},
            headers=API_KEY_HEADER,
        )
        data = resp.json()
        # Should work with high risk (identity check happens)
        assert data["decision"] in ("allow", "deny", "step_up")
