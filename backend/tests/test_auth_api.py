import pytest


@pytest.mark.asyncio
async def test_register_and_login_and_me(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "password1"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]

    r = await client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "password1"},
    )
    assert r.status_code == 200

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password1"},
    )
    r = await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password1"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_invalid(client):
    r = await client.post(
        "/api/auth/login",
        json={"email": "nope@example.com", "password": "password1"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_missing_token(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_bad_token(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer bogus"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_non_bearer(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Basic xxx"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
