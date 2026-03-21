import pytest_asyncio
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.dependencies import get_transport
from backend.app.services.transport.base import TransportBase
from backend.app.schemas.auth import VerificationPayload
from backend.app.schemas.enrollment import EnrollmentPayload
from backend.app.services.vector_store_service import vector_store


# ── Test database (in-memory SQLite) ──

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with test_async_session() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Mock transport ──

def _make_embedding(dim: int = 64) -> list[float]:
    vec = np.random.default_rng(42).standard_normal(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


ENROLLED_EMBEDDING = _make_embedding()


class MockTransport(TransportBase):
    """Mock edge device that returns predictable payloads."""

    def __init__(
        self,
        embedding: list[float] | None = None,
        bpm: float = 74.0,
        hrv: float = 40.0,
        signal_quality: float = 0.95,
        should_fail: bool = False,
    ):
        self._embedding = embedding or ENROLLED_EMBEDDING
        self._bpm = bpm
        self._hrv = hrv
        self._signal_quality = signal_quality
        self._should_fail = should_fail

    async def request_verification(self, user_id: str) -> VerificationPayload:
        if self._should_fail:
            raise ConnectionError("Edge device unreachable")
        return VerificationPayload(
            user_id=user_id,
            mode="verify",
            embedding=self._embedding,
            bpm=self._bpm,
            hrv=self._hrv,
            signal_quality=self._signal_quality,
            timestamp="2026-03-21T18:30:00Z",
        )

    async def request_enrollment(self, user_id: str) -> EnrollmentPayload:
        if self._should_fail:
            raise ConnectionError("Edge device unreachable")
        return EnrollmentPayload(
            user_id=user_id,
            mode="enroll",
            embedding=self._embedding,
            bpm=self._bpm,
            hrv=self._hrv,
            signal_quality=self._signal_quality,
            timestamp="2026-03-21T18:30:00Z",
        )

    async def health_check(self) -> bool:
        return not self._should_fail


def make_mock_transport(**kwargs) -> MockTransport:
    return MockTransport(**kwargs)


# ── Test HTTP client ──

@pytest_asyncio.fixture
async def client(db_session):
    """Async test client with overridden DB and transport dependencies."""
    vector_store.reset()
    mock_transport = MockTransport()

    async def override_get_db():
        yield db_session

    def override_get_transport():
        return mock_transport

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_transport] = override_get_transport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_transport(db_session):
    """Factory fixture: returns a function to create client with custom transport."""
    vector_store.reset()

    async def _make_client(**transport_kwargs):
        mock = MockTransport(**transport_kwargs)

        async def override_get_db():
            yield db_session

        def override_get_transport():
            return mock

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_transport] = override_get_transport

        transport = ASGITransport(app=app)
        ac = AsyncClient(transport=transport, base_url="http://test")
        return ac

    yield _make_client
    app.dependency_overrides.clear()


API_KEY_HEADER = {"X-API-Key": "dev-api-key-001"}
