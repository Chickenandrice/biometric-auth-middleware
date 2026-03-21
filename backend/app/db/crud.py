from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from backend.app.db.models import User, Baseline, Policy, AuditLog


# ── Users ──

async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def create_user(db: AsyncSession, user_id: str, display_name: str | None = None) -> User:
    user = User(user_id=user_id, display_name=display_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_enrolled(db: AsyncSession, user_id: str, enrolled: bool) -> User | None:
    user = await get_user(db, user_id)
    if not user:
        return None
    user.enrolled = enrolled
    user.enrolled_at = datetime.datetime.now(datetime.timezone.utc) if enrolled else None
    await db.commit()
    await db.refresh(user)
    return user


# ── Baselines ──

async def get_baseline(db: AsyncSession, user_id: str) -> Baseline | None:
    result = await db.execute(select(Baseline).where(Baseline.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_baseline(
    db: AsyncSession,
    user_id: str,
    bpm_mean: float,
    bpm_std: float,
    hrv_mean: float,
    hrv_std: float,
    sample_count: int = 1,
) -> Baseline:
    existing = await get_baseline(db, user_id)
    if existing:
        existing.bpm_mean = bpm_mean
        existing.bpm_std = bpm_std
        existing.hrv_mean = hrv_mean
        existing.hrv_std = hrv_std
        existing.sample_count = sample_count
        await db.commit()
        await db.refresh(existing)
        return existing
    baseline = Baseline(
        user_id=user_id,
        bpm_mean=bpm_mean,
        bpm_std=bpm_std,
        hrv_mean=hrv_mean,
        hrv_std=hrv_std,
        sample_count=sample_count,
    )
    db.add(baseline)
    await db.commit()
    await db.refresh(baseline)
    return baseline


# ── Policies ──

async def get_policy(db: AsyncSession, action: str) -> Policy | None:
    result = await db.execute(select(Policy).where(Policy.action == action))
    return result.scalar_one_or_none()


async def list_policies(db: AsyncSession) -> list[Policy]:
    result = await db.execute(select(Policy).order_by(Policy.action))
    return list(result.scalars().all())


async def upsert_policy(
    db: AsyncSession,
    action: str,
    risk_level: str = "high",
    identity_threshold: float | None = None,
    anomaly_threshold: float | None = None,
) -> Policy:
    existing = await get_policy(db, action)
    if existing:
        existing.risk_level = risk_level
        existing.identity_threshold = identity_threshold
        existing.anomaly_threshold = anomaly_threshold
        await db.commit()
        await db.refresh(existing)
        return existing
    policy = Policy(
        action=action,
        risk_level=risk_level,
        identity_threshold=identity_threshold,
        anomaly_threshold=anomaly_threshold,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


# ── Audit Logs ──

async def create_audit_log(db: AsyncSession, **kwargs) -> AuditLog:
    log = AuditLog(**kwargs)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_audit_logs(
    db: AsyncSession,
    user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    result = await db.execute(query)
    return list(result.scalars().all())
