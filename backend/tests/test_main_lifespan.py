import pytest
from mongomock_motor import AsyncMongoMockClient


@pytest.mark.asyncio
async def test_lifespan_startup_handles_index_errors(monkeypatch):
    from app import database, main

    client = AsyncMongoMockClient()
    database._db.client = client
    database._db.db = client["test_lifespan"]

    async def raise_indexes():
        raise RuntimeError("cannot build indexes")

    monkeypatch.setattr(main, "ensure_indexes", raise_indexes)

    app = main.create_app()
    async with main.lifespan(app):
        pass  # should swallow error


@pytest.mark.asyncio
async def test_lifespan_startup_success(monkeypatch):
    from app import database, main

    client = AsyncMongoMockClient()
    database._db.client = client
    database._db.db = client["test_lifespan2"]

    called = {"n": 0}

    async def ok_indexes():
        called["n"] += 1

    monkeypatch.setattr(main, "ensure_indexes", ok_indexes)

    app = main.create_app()
    async with main.lifespan(app):
        pass
    assert called["n"] == 1
