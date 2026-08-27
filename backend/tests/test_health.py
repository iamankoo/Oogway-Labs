from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]


async def test_readiness_reports_degraded_when_database_unreachable(client: AsyncClient) -> None:
    # The fixture points at a non-existent host, so readiness must report
    # a degraded status rather than raising or lying about health.
    response = await client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    dependency_names = {dep["name"] for dep in body["dependencies"]}
    assert "postgresql" in dependency_names
    postgres_dep = next(dep for dep in body["dependencies"] if dep["name"] == "postgresql")
    assert postgres_dep["status"] == "error"
