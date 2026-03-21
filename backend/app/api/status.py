from fastapi import APIRouter, Depends

from backend.app.config import settings
from backend.app.dependencies import get_transport
from backend.app.utils.security import verify_api_key

router = APIRouter(tags=["status"])


@router.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "ok", "service": settings.app_name}


@router.get("/status")
async def system_status(
    transport=Depends(get_transport),
    _api_key: str = Depends(verify_api_key),
):
    """Check system status including edge device connectivity."""
    edge_ok = await transport.health_check()
    return {
        "service": settings.app_name,
        "transport_mode": settings.transport_mode,
        "edge_connected": edge_ok,
    }
