from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from web_gui_agent.api.server import create_app
from web_gui_agent.config.settings import Settings


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app(settings=Settings())
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://testserver") as api_client:
            yield api_client


async def test_health_check_is_available(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_then_query_task(client: AsyncClient) -> None:
    created = await client.post(
        "/tasks",
        json={
            "instruction": "Search the controlled test site",
            "start_url": "https://example.test/search",
        },
    )
    task_id = created.json()["id"]
    fetched = await client.get(f"/tasks/{task_id}")

    assert created.status_code == 201
    assert created.json()["status"] == "QUEUED"
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task_id
    assert fetched.json()["status"] == "QUEUED"


async def test_invalid_create_request_returns_clear_4xx(client: AsyncClient) -> None:
    response = await client.post("/tasks", json={"instruction": " ", "unexpected": True})

    assert response.status_code == 422
    details = response.json()["detail"]
    assert len(details) >= 1


async def test_unknown_task_returns_structured_not_found_error(client: AsyncClient) -> None:
    response = await client.get("/tasks/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "TASK_NOT_FOUND"


async def test_queued_task_can_be_cancelled_once(client: AsyncClient) -> None:
    created = await client.post("/tasks", json={"instruction": "Search"})
    task_id = created.json()["id"]
    cancelled = await client.delete(f"/tasks/{task_id}")
    repeated = await client.delete(f"/tasks/{task_id}")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "INVALID_STATE_TRANSITION"
