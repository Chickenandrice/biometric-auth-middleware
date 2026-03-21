from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.enrollment import EnrollRequest, EnrollResponse
from backend.app.services.enrollment_service import enrollment_service
from backend.app.utils.security import verify_api_key
from backend.app.dependencies import get_transport

router = APIRouter(tags=["enrollment"])


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(
    request: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    transport=Depends(get_transport),
    _api_key: str = Depends(verify_api_key),
):
    """Enroll a user by capturing their ECG baseline."""
    return await enrollment_service.enroll_user(request.user_id, transport, db)


@router.post("/unenroll", response_model=EnrollResponse)
async def unenroll(
    request: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """Remove a user's enrollment."""
    return await enrollment_service.unenroll_user(request.user_id, db)
