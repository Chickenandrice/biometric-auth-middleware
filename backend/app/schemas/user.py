from pydantic import BaseModel
from datetime import datetime


class UserCreate(BaseModel):
    user_id: str
    display_name: str | None = None


class UserOut(BaseModel):
    user_id: str
    display_name: str | None
    enrolled: bool
    enrolled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
