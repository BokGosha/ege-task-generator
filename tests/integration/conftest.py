"""
Общие фикстуры для интеграционных тестов.
Используют реальную PostgreSQL БД из DATABASE_URL.
"""

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.core.rate_limit import limiter
from backend.app.main import app

settings.llm_generation_provider = "mock"
settings.llm_validation_provider = "mock"

pytestmark = [pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Сбрасывает счётчики slowapi перед каждым тестом."""

    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def test_engine():
    """Движок БД, создаваемый в текущем event loop."""

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
