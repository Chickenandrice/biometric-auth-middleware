import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.db.session import init_db, async_session
from backend.app.dependencies import get_transport
from backend.app.api import authorize, enroll, users, logs, status, relay

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DASHBOARD_DIR = _REPO_ROOT / "frontend" / "dashboard"


async def _auto_enroll_operator():
    """In simulate mode, auto-enroll an 'operator' user so the demo works out of the box."""
    from backend.app.services.enrollment_service import enrollment_service
    transport = get_transport()
    async with async_session() as db:
        await enrollment_service.enroll_user("operator", transport, db)
    logger.info("Simulate mode: auto-enrolled 'operator'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)
    await init_db()
    if settings.transport_mode == "simulate":
        await _auto_enroll_operator()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="Biometric step-up authentication middleware using live ECG signals",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Serve the dashboard UI; API remains at `/health`, `/users`, `/docs`, etc."""
    return RedirectResponse(url="/dashboard/", status_code=307)


# Register routes
app.include_router(authorize.router)
app.include_router(enroll.router)
app.include_router(users.router)
app.include_router(logs.router)
app.include_router(status.router)
app.include_router(relay.router)

if _DASHBOARD_DIR.is_dir():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
        name="dashboard",
    )
else:
    logger.warning("Dashboard not mounted: missing directory %s", _DASHBOARD_DIR)
