import pytest

from app import deps
from app.services import rate_limit


@pytest.mark.asyncio
async def test_rate_limit_dep_allows(monkeypatch):
    rate_limit.reset()

    class DummyReq:
        class client:
            host = "1.2.3.4"

    req = DummyReq()
    # Default allowed
    await deps.rate_limit(req, user=None)  # should not raise


@pytest.mark.asyncio
async def test_rate_limit_dep_blocks(monkeypatch):
    class DummyReq:
        class client:
            host = "1.2.3.4"

    monkeypatch.setattr(deps, "check_rate_limit", lambda *a, **k: False)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await deps.rate_limit(DummyReq(), user=None)


@pytest.mark.asyncio
async def test_rate_limit_dep_no_client(monkeypatch):
    class DummyReq:
        client = None

    rate_limit.reset()
    await deps.rate_limit(DummyReq(), user=None)


@pytest.mark.asyncio
async def test_user_rate_limit_blocks(monkeypatch):
    monkeypatch.setattr(deps, "check_rate_limit", lambda *a, **k: False)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await deps.user_rate_limit(user={"id": "u1"})


@pytest.mark.asyncio
async def test_user_rate_limit_allows(monkeypatch):
    monkeypatch.setattr(deps, "check_rate_limit", lambda *a, **k: True)
    out = await deps.user_rate_limit(user={"id": "u1"})
    assert out == {"id": "u1"}


@pytest.mark.asyncio
async def test_get_current_user_token_without_sub(monkeypatch, db):
    from app.services.security import create_access_token

    # Forge a token that lacks sub by patching decode_token
    import app.deps as deps_mod

    monkeypatch.setattr(deps_mod, "decode_token", lambda t: {"foo": "bar"})
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await deps_mod.get_current_user(authorization="Bearer whatever")


@pytest.mark.asyncio
async def test_get_current_user_invalid_object_id(monkeypatch, db):
    import app.deps as deps_mod

    monkeypatch.setattr(deps_mod, "decode_token", lambda t: {"sub": "not-an-oid"})
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await deps_mod.get_current_user(authorization="Bearer whatever")
