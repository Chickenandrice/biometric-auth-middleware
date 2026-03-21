import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import crud
from backend.app.schemas.enrollment import EnrollmentPayload, EnrollResponse
from backend.app.services.vector_store_service import vector_store
from backend.app.services.transport.base import TransportBase

logger = logging.getLogger(__name__)


class EnrollmentService:
    """Orchestrates the enrollment flow."""

    async def enroll_user(
        self,
        user_id: str,
        transport: TransportBase,
        db: AsyncSession,
    ) -> EnrollResponse:
        # Ensure user exists
        user = await crud.get_user(db, user_id)
        if not user:
            user = await crud.create_user(db, user_id)

        # Request enrollment capture from edge device
        payload: EnrollmentPayload = await transport.request_enrollment(user_id)

        if payload.signal_quality < 0.5:
            return EnrollResponse(
                user_id=user_id,
                enrolled=False,
                message="Signal quality too low for enrollment. Please try again.",
            )

        # Store embedding in vector DB
        vector_store.store_embedding(
            user_id=user_id,
            embedding=payload.embedding,
            metadata={"bpm": payload.bpm, "hrv": payload.hrv, "timestamp": payload.timestamp},
        )

        # Store baseline stats in SQL DB
        await crud.upsert_baseline(
            db,
            user_id=user_id,
            bpm_mean=payload.bpm,
            bpm_std=payload.bpm * 0.1,  # Initial estimate; refine with more samples
            hrv_mean=payload.hrv,
            hrv_std=payload.hrv * 0.15,
            sample_count=1,
        )

        # Mark user as enrolled
        await crud.set_user_enrolled(db, user_id, True)

        logger.info("User %s enrolled successfully", user_id)
        return EnrollResponse(
            user_id=user_id,
            enrolled=True,
            message="Enrollment successful.",
        )

    async def unenroll_user(self, user_id: str, db: AsyncSession) -> EnrollResponse:
        vector_store.delete_embedding(user_id)
        await crud.set_user_enrolled(db, user_id, False)
        return EnrollResponse(
            user_id=user_id,
            enrolled=False,
            message="User unenrolled.",
        )


enrollment_service = EnrollmentService()
