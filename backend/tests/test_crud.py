"""Tests for database CRUD operations."""

import pytest
import pytest_asyncio

from backend.app.db import crud
from backend.tests.conftest import db_session


# ── Users ──

class TestUserCrud:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        user = await crud.create_user(db_session, "alice", "Alice Chen")
        assert user.user_id == "alice"
        assert user.display_name == "Alice Chen"
        assert user.enrolled is False
        assert user.enrolled_at is None

    @pytest.mark.asyncio
    async def test_create_user_no_display_name(self, db_session):
        user = await crud.create_user(db_session, "bob")
        assert user.display_name is None

    @pytest.mark.asyncio
    async def test_get_user(self, db_session):
        await crud.create_user(db_session, "alice")
        user = await crud.get_user(db_session, "alice")
        assert user is not None
        assert user.user_id == "alice"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, db_session):
        user = await crud.get_user(db_session, "nonexistent")
        assert user is None

    @pytest.mark.asyncio
    async def test_list_users(self, db_session):
        await crud.create_user(db_session, "alice")
        await crud.create_user(db_session, "bob")
        users = await crud.list_users(db_session)
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_set_user_enrolled(self, db_session):
        await crud.create_user(db_session, "alice")
        user = await crud.set_user_enrolled(db_session, "alice", True)
        assert user.enrolled is True
        assert user.enrolled_at is not None

    @pytest.mark.asyncio
    async def test_set_user_unenrolled(self, db_session):
        await crud.create_user(db_session, "alice")
        await crud.set_user_enrolled(db_session, "alice", True)
        user = await crud.set_user_enrolled(db_session, "alice", False)
        assert user.enrolled is False
        assert user.enrolled_at is None

    @pytest.mark.asyncio
    async def test_set_enrolled_nonexistent_user(self, db_session):
        result = await crud.set_user_enrolled(db_session, "ghost", True)
        assert result is None


# ── Baselines ──

class TestBaselineCrud:
    @pytest.mark.asyncio
    async def test_upsert_baseline_create(self, db_session):
        bl = await crud.upsert_baseline(db_session, "alice", 72.0, 6.0, 42.0, 8.0)
        assert bl.user_id == "alice"
        assert bl.bpm_mean == 72.0

    @pytest.mark.asyncio
    async def test_upsert_baseline_update(self, db_session):
        await crud.upsert_baseline(db_session, "alice", 72.0, 6.0, 42.0, 8.0)
        bl = await crud.upsert_baseline(db_session, "alice", 75.0, 5.0, 45.0, 7.0, sample_count=2)
        assert bl.bpm_mean == 75.0
        assert bl.sample_count == 2

    @pytest.mark.asyncio
    async def test_get_baseline(self, db_session):
        await crud.upsert_baseline(db_session, "alice", 72.0, 6.0, 42.0, 8.0)
        bl = await crud.get_baseline(db_session, "alice")
        assert bl is not None
        assert bl.hrv_mean == 42.0

    @pytest.mark.asyncio
    async def test_get_baseline_not_found(self, db_session):
        bl = await crud.get_baseline(db_session, "ghost")
        assert bl is None


# ── Policies ──

class TestPolicyCrud:
    @pytest.mark.asyncio
    async def test_upsert_policy_create(self, db_session):
        p = await crud.upsert_policy(db_session, "approve_transfer", "critical")
        assert p.action == "approve_transfer"
        assert p.risk_level == "critical"

    @pytest.mark.asyncio
    async def test_upsert_policy_update(self, db_session):
        await crud.upsert_policy(db_session, "approve_transfer", "high")
        p = await crud.upsert_policy(db_session, "approve_transfer", "critical", identity_threshold=0.9)
        assert p.risk_level == "critical"
        assert p.identity_threshold == 0.9

    @pytest.mark.asyncio
    async def test_list_policies(self, db_session):
        await crud.upsert_policy(db_session, "transfer", "high")
        await crud.upsert_policy(db_session, "delete", "critical")
        policies = await crud.list_policies(db_session)
        assert len(policies) == 2

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, db_session):
        p = await crud.get_policy(db_session, "nonexistent")
        assert p is None


# ── Audit Logs ──

class TestAuditLogCrud:
    @pytest.mark.asyncio
    async def test_create_audit_log(self, db_session):
        log = await crud.create_audit_log(
            db_session,
            user_id="alice",
            action="approve_transfer",
            decision="allow",
            confidence=0.91,
            reason_codes=["IDENTITY_MATCH"],
        )
        assert log.id is not None
        assert log.decision == "allow"

    @pytest.mark.asyncio
    async def test_list_audit_logs(self, db_session):
        for i in range(5):
            await crud.create_audit_log(
                db_session, user_id="alice", decision="allow",
            )
        logs = await crud.list_audit_logs(db_session)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_list_audit_logs_filter_by_user(self, db_session):
        await crud.create_audit_log(db_session, user_id="alice", decision="allow")
        await crud.create_audit_log(db_session, user_id="bob", decision="deny")
        logs = await crud.list_audit_logs(db_session, user_id="alice")
        assert len(logs) == 1
        assert logs[0].user_id == "alice"

    @pytest.mark.asyncio
    async def test_list_audit_logs_pagination(self, db_session):
        for i in range(10):
            await crud.create_audit_log(db_session, user_id="alice", decision="allow")
        page1 = await crud.list_audit_logs(db_session, limit=3, offset=0)
        page2 = await crud.list_audit_logs(db_session, limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].id != page2[0].id
