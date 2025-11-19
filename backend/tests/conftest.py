from collections.abc import Generator, AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import async_engine, init_db
from app.main import app
from app.models import Item, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession,None]:
    async with AsyncSession(async_engine) as session:
        await init_db(session)
        await session.commit()
        yield session
        await session.rollback()



@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def superuser_token_headers(client: AsyncClient) -> dict[str, str]:
    return await get_superuser_token_headers(client)


@pytest_asyncio.fixture(scope="function")
async def normal_user_token_headers(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    return await authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest_asyncio.fixture(scope="function")
async def client_with_test_db(db: AsyncSession, client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """
    Wraps the client and overrides the DB session to use the test session.
    """
    async def _override_get_session():
        yield db  # Reuse the same session

    app.dependency_overrides[get_db] = _override_get_session
    yield client
    app.dependency_overrides.clear()