from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError, NotFoundError, register_exception_handlers


async def _build_test_client() -> AsyncClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/app-error")
    async def boom_app_error() -> None:
        raise AppError("custom failure", details={"field": "value"})

    @app.get("/boom/not-found")
    async def boom_not_found() -> None:
        raise NotFoundError()

    @app.get("/boom/unexpected")
    async def boom_unexpected() -> None:
        raise RuntimeError("kaboom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://testserver")


async def test_app_error_returns_structured_envelope() -> None:
    async with await _build_test_client() as client:
        response = await client.get("/boom/app-error")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "custom failure"
    assert body["error"]["details"] == {"field": "value"}


async def test_not_found_error_maps_to_404() -> None:
    async with await _build_test_client() as client:
        response = await client.get("/boom/not-found")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_unexpected_exception_hides_internal_details() -> None:
    async with await _build_test_client() as client:
        response = await client.get("/boom/unexpected")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "kaboom" not in body["error"]["message"]
