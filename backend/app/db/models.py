from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, JSON
from sqlalchemy.sql import func

from backend.app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), unique=True, nullable=False, index=True)
    display_name = Column(String(256), nullable=True)
    enrolled = Column(Boolean, default=False, nullable=False)
    enrolled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Baseline(Base):
    __tablename__ = "baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    bpm_mean = Column(Float, nullable=False)
    bpm_std = Column(Float, nullable=False)
    hrv_mean = Column(Float, nullable=False)
    hrv_std = Column(Float, nullable=False)
    sample_count = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(256), unique=True, nullable=False)
    risk_level = Column(String(32), nullable=False, default="high")  # low, high, critical
    identity_threshold = Column(Float, nullable=True)
    anomaly_threshold = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    action = Column(String(256), nullable=True)
    decision = Column(String(32), nullable=False)  # allow, deny, step_up
    confidence = Column(Float, nullable=True)
    reason_codes = Column(JSON, nullable=True)
    similarity_score = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    signal_quality = Column(Float, nullable=True)
    bpm = Column(Float, nullable=True)
    hrv = Column(Float, nullable=True)
    transport_mode = Column(String(32), nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
