from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.auth import AuthorizeRequest, AuthorizeResponse
from backend.app.services.auth_service import auth_service
from backend.app.utils.security import verify_api_key
from backend.app.dependencies import get_transport

router = APIRouter(tags=["authorize"])


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: AuthorizeRequest,
    db: AsyncSession = Depends(get_db),
    transport=Depends(get_transport),
    _api_key: str = Depends(verify_api_key),
):
    """Authorize a sensitive action via biometric verification."""
    return await auth_service.authorize(request, transport, db)
