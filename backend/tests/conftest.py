import os

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb_test",
)

import asyncio  # noqa: E402
from typing import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    # pytest-asyncio 0.23 defaults to a fresh event loop per test function. The app's
    # own module-level engine (app.core.database.engine, used internally by
    # IngestionService via AsyncSessionLocal) is created once at import time and pools
    # connections - reusing that pool from a later test's new loop corrupts asyncpg's
    # connection state ("cannot perform operation: another operation is in progress").
    # Pinning the loop to session scope keeps every engine on one consistent loop.
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    # NullPool: even within one event loop, SQLAlchemy's greenlet-based async bridge
    # left pooled asyncpg connections in a corrupted state across fixture teardown
    # boundaries in this session-scoped-engine + function-scoped-session setup
    # (same InterfaceError as above). Reproduced and confirmed in isolation - opening
    # a fresh, unpooled connection per checkout avoids the corruption entirely.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-API-Key": settings.API_KEY}
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def valid_txt_bytes() -> bytes:
    return b"The quick brown fox jumps over the lazy dog. " * 20
