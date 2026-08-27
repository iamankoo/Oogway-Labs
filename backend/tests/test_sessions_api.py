from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DEMO_USER_ID, ChatSession


async def test_create_session_assigns_the_single_demo_user(
    client: AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post("/api/sessions")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New conversation"
    assert uuid.UUID(body["id"])

    async with db_sessionmaker() as db:
        stored = (await db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(body["id"])))).scalar_one()
        assert stored.user_id == DEMO_USER_ID


async def test_list_sessions_orders_most_recently_active_first(client: AsyncClient) -> None:
    first = (await client.post("/api/sessions")).json()
    second = (await client.post("/api/sessions")).json()

    # Sending a message to the first session bumps its updated_at, so it
    # should sort ahead of the second session despite being created first.
    await client.post(f"/api/sessions/{first['id']}/messages", json={"content": "hello"})

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert ids.index(first["id"]) < ids.index(second["id"])


async def test_get_session_returns_404_for_unknown_session(client: AsyncClient) -> None:
    response = await client.get(f"/api/sessions/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


async def test_create_message_persists_and_bumps_session(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()

    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "What is PMF?"})
    assert response.status_code == 201
    body = response.json()
    assert body["message"]["role"] == "user"
    assert body["message"]["content"] == "What is PMF?"
    assert body["message"]["session_id"] == session["id"]
    # First user message deterministically becomes the session title.
    assert body["session"]["title"] == "What is PMF?"


async def test_long_first_message_is_truncated_into_a_title(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()
    long_content = "How should I think about growth loops " * 5

    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": long_content})
    title = response.json()["session"]["title"]
    assert len(title) <= 61  # 60 chars + ellipsis
    assert title.endswith("…")


async def test_second_message_does_not_overwrite_title(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "first question"})
    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "second question"})

    assert response.json()["session"]["title"] == "first question"


async def test_list_messages_returns_messages_in_chronological_order(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "one"})
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "two"})

    response = await client.get(f"/api/sessions/{session['id']}/messages")
    assert response.status_code == 200
    # Each send also produces a stubbed assistant reply (autouse fixture) -
    # filter to the user's own turns to check *their* ordering specifically.
    user_contents = [m["content"] for m in response.json() if m["role"] == "user"]
    assert user_contents == ["one", "two"]


async def test_session_isolation_between_two_sessions(client: AsyncClient) -> None:
    session_a = (await client.post("/api/sessions")).json()
    session_b = (await client.post("/api/sessions")).json()

    await client.post(f"/api/sessions/{session_a['id']}/messages", json={"content": "message in A"})
    await client.post(f"/api/sessions/{session_b['id']}/messages", json={"content": "message in B"})

    messages_a = (await client.get(f"/api/sessions/{session_a['id']}/messages")).json()
    messages_b = (await client.get(f"/api/sessions/{session_b['id']}/messages")).json()

    user_contents_a = [m["content"] for m in messages_a if m["role"] == "user"]
    user_contents_b = [m["content"] for m in messages_b if m["role"] == "user"]
    assert user_contents_a == ["message in A"]
    assert user_contents_b == ["message in B"]
    # The assistant's replies are isolated too, not just the user's turns.
    assert all(m["session_id"] == session_a["id"] for m in messages_a)
    assert all(m["session_id"] == session_b["id"] for m in messages_b)


async def test_create_message_for_unknown_session_returns_404(client: AsyncClient) -> None:
    response = await client.post(f"/api/sessions/{uuid.uuid4()}/messages", json={"content": "hello"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


async def test_list_messages_for_unknown_session_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/sessions/{uuid.uuid4()}/messages")
    assert response.status_code == 404


async def test_create_message_rejects_empty_content(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()
    response = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_create_message_rejects_non_user_role(client: AsyncClient) -> None:
    session = (await client.post("/api/sessions")).json()
    response = await client.post(
        f"/api/sessions/{session['id']}/messages", json={"role": "assistant", "content": "faked reply"}
    )
    assert response.status_code == 422
