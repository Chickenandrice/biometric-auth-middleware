from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db import crud
from backend.app.schemas.log import AuditLogOut
from backend.app.utils.security import verify_api_key

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[AuditLogOut])
async def list_logs(
    user_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """List audit logs, optionally filtered by user_id."""
    return await crud.list_audit_logs(db, user_id=user_id, limit=limit, offset=offset)
