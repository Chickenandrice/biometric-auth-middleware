from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db import crud
from backend.app.schemas.user import UserCreate, UserOut
from backend.app.utils.security import verify_api_key

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    return await crud.list_users(db)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    existing = await crud.get_user(db, body.user_id)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    return await crud.create_user(db, body.user_id, body.display_name)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    user = await crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
