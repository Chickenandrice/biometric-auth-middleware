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
        return await self.enroll_from_payload(user_id, payload, db)

    async def enroll_from_payload(
        self,
        user_id: str,
        payload: EnrollmentPayload,
        db: AsyncSession,
    ) -> EnrollResponse:
        """Apply enrollment from a payload (e.g. BLE/Web relay from admin app or SDK)."""
        user = await crud.get_user(db, user_id)
        if not user:
            user = await crud.create_user(db, user_id)

        if payload.signal_quality < 0.5:
            return EnrollResponse(
                user_id=user_id,
                enrolled=False,
                message="Signal quality too low for enrollment. Please try again.",
            )

        # Store embedding in vector DB
        try:
            vector_store.store_embedding(
                user_id=user_id,
                embedding=payload.embedding,
                metadata={
                    "bpm": payload.bpm,
                    "hrv": payload.hrv,
                    "timestamp": payload.timestamp,
                },
            )
        except Exception as e:
            logger.exception("Vector store enrollment failed for user_id=%s", user_id)
            hint = (
                " Often the collection was built with a different embedding length: "
                "stop the server, delete the Chroma folder (default ./chroma_data or "
                "BIOAUTH_CHROMA_PERSIST_DIR), then restart."
            )
            raise RuntimeError(f"{e!s}.{hint}") from e

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
