from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app


async def _client_with_db(db_session, headers=None) -> AsyncClient:
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", headers=headers or {})


async def test_missing_api_key_is_rejected(db_session):
    async with await _client_with_db(db_session) as ac:
        response = await ac.get("/api/v1/documents/")
    app.dependency_overrides.clear()

    assert response.status_code == 422  # missing required header


async def test_wrong_api_key_is_rejected(db_session):
    async with await _client_with_db(db_session, headers={"X-API-Key": "wrong-key"}) as ac:
        response = await ac.get("/api/v1/documents/")
    app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_correct_api_key_is_accepted(client):
    response = await client.get("/api/v1/documents/")
    assert response.status_code == 200


async def test_health_check_does_not_require_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "rag-enterprise-assistant"}
