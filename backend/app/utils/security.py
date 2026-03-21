from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from backend.app.config import settings

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Validate the API key from request headers."""
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
