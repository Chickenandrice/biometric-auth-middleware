import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db import crud
from backend.app.schemas.auth import AuthorizeRequest, AuthorizeResponse, VerificationPayload
from backend.app.services.scoring_service import scoring_service
from backend.app.services.vector_store_service import vector_store
from backend.app.services.transport.base import TransportBase
from backend.app.utils.thresholds import get_identity_threshold, get_anomaly_threshold

logger = logging.getLogger(__name__)


class AuthService:
    """Orchestrates the authorization / verification flow."""

    async def authorize(
        self,
        request: AuthorizeRequest,
        transport: TransportBase,
        db: AsyncSession,
    ) -> AuthorizeResponse:
        reason_codes: list[str] = []
        risk_level = request.risk_level

        # ── Low-risk: no biometric needed ──
        if risk_level == "low":
            return AuthorizeResponse(
                decision="allow",
                confidence=1.0,
                reason_codes=["LOW_RISK_BYPASS"],
            )

        # ── Check enrollment ──
        user = await crud.get_user(db, request.user_id)
        if not user or not user.enrolled:
            return AuthorizeResponse(
                decision="deny",
                confidence=0.0,
                reason_codes=["NOT_ENROLLED"],
            )

        enrolled_embedding = vector_store.get_embedding(request.user_id)
        if not enrolled_embedding:
            return AuthorizeResponse(
                decision="deny",
                confidence=0.0,
                reason_codes=["NO_TEMPLATE"],
            )

        # ── Get policy overrides ──
        policy = await crud.get_policy(db, request.action)
        id_thresh = get_identity_threshold(
            risk_level, policy.identity_threshold if policy else None
        )
        anom_thresh = get_anomaly_threshold(
            risk_level, policy.anomaly_threshold if policy else None
        )

        # ── Request live verification from edge device ──
        try:
            payload: VerificationPayload = await transport.request_verification(
                request.user_id
            )
        except Exception as exc:
            logger.error("Transport error: %s", exc)
            return AuthorizeResponse(
                decision="step_up",
                confidence=0.0,
                reason_codes=["TRANSPORT_ERROR"],
            )

        # ── Signal quality check ──
        if payload.signal_quality < settings.signal_quality_threshold:
            reason_codes.append("POOR_SIGNAL")
            await self._log_decision(
                db, request, "step_up", 0.0, reason_codes,
                signal_quality=payload.signal_quality, bpm=payload.bpm, hrv=payload.hrv,
            )
            return AuthorizeResponse(
                decision="step_up",
                confidence=payload.signal_quality,
                reason_codes=reason_codes,
            )

        # ── Identity similarity ──
        identity_score = scoring_service.compute_identity_score(
            payload.embedding, enrolled_embedding
        )
        if identity_score < id_thresh:
            reason_codes.append("IDENTITY_MISMATCH")

        # ── Anomaly score ──
        baseline = await crud.get_baseline(db, request.user_id)
        anomaly_score = 0.0
        if baseline and risk_level == "critical":
            anomaly_score = scoring_service.compute_anomaly_score(
                payload.bpm, payload.hrv, baseline
            )
            if anomaly_score > anom_thresh:
                reason_codes.append("ANOMALY_DETECTED")

        # ── Decision ──
        if "IDENTITY_MISMATCH" in reason_codes or "ANOMALY_DETECTED" in reason_codes:
            decision = "deny"
            confidence = identity_score
        else:
            decision = "allow"
            confidence = identity_score
            reason_codes.append("IDENTITY_MATCH")

        await self._log_decision(
            db, request, decision, confidence, reason_codes,
            similarity_score=identity_score,
            anomaly_score=anomaly_score,
            signal_quality=payload.signal_quality,
            bpm=payload.bpm,
            hrv=payload.hrv,
        )

        return AuthorizeResponse(
            decision=decision,
            confidence=round(confidence, 4),
            reason_codes=reason_codes,
        )

    async def _log_decision(
        self,
        db: AsyncSession,
        request: AuthorizeRequest,
        decision: str,
        confidence: float,
        reason_codes: list[str],
        **extra,
    ):
        await crud.create_audit_log(
            db,
            user_id=request.user_id,
            action=request.action,
            decision=decision,
            confidence=confidence,
            reason_codes=reason_codes,
            transport_mode=settings.transport_mode,
            **extra,
        )


auth_service = AuthService()
