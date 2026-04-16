import pytest


def test_settings_upload_path_and_cors():
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    p = s.upload_path
    assert p.exists()
    assert isinstance(s.cors_origin_list, list)


@pytest.mark.asyncio
async def test_get_db_singleton_and_close(monkeypatch):
    from app import database

    database._db.client = None
    database._db.db = None
    # get_client/get_db will try to build real client; substitute with mock
    from mongomock_motor import AsyncMongoMockClient

    client = AsyncMongoMockClient()
    database._db.client = client
    database._db.db = None
    dbx = database.get_db()
    assert dbx is not None
    # second call returns cached
    dbx2 = database.get_db()
    assert dbx is dbx2
    await database.close_db()
    assert database._db.client is None


@pytest.mark.asyncio
async def test_set_db_override():
    from app import database
    from mongomock_motor import AsyncMongoMockClient

    client = AsyncMongoMockClient()
    database.set_db(client["override"])
    assert database.get_db().name == "override"
    database._db.db = None


def test_rate_limit_dep_function_signature_imports():
    # sanity: the deps module imports and contains the callables we reference
    from app import deps

    assert callable(deps.rate_limit)
    assert callable(deps.user_rate_limit)
    assert callable(deps.get_current_user)
