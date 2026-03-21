"""Relay endpoints: enrollment / verification payloads from BLE clients (Web Bluetooth, SDK + bleak)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.auth import AuthorizeResponse, AuthorizeRequest, RelayAuthorizeBody
from backend.app.schemas.enrollment import EnrollmentPayload, EnrollResponse
from backend.app.services.auth_service import auth_service
from backend.app.services.enrollment_service import enrollment_service
from backend.app.utils.security import verify_api_key

router = APIRouter(prefix="/relay", tags=["relay"])


@router.post("/enrollment", response_model=EnrollResponse)
async def relay_enrollment(
    payload: EnrollmentPayload,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """
    Apply enrollment from JSON captured over BLE/Web Bluetooth and forwarded by the admin UI or SDK.
    Body must match EnrollmentPayload (same shape edge HTTP transport returns).
    """
    try:
        return await enrollment_service.enroll_from_payload(
            payload.user_id, payload, db
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        logger.exception("relay_enrollment failed")
        raise


@router.post("/authorize", response_model=AuthorizeResponse)
async def relay_authorize(
    body: RelayAuthorizeBody,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """
    Run /authorize scoring using verification JSON from the edge relayed by the SDK (or admin tool).
    """
    if body.verification.user_id != body.user_id:
        raise HTTPException(
            status_code=400,
            detail="verification.user_id must match user_id",
        )
    req = AuthorizeRequest(
        user_id=body.user_id,
        action=body.action,
        risk_level=body.risk_level,
    )
    return await auth_service.authorize_with_payload(
        req, body.verification, db
    )
