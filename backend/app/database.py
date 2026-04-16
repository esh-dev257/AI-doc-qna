from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings


class Database:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


_db = Database()


def get_client() -> AsyncIOMotorClient:
    if _db.client is None:
        settings = get_settings()
        _db.client = AsyncIOMotorClient(settings.mongo_uri)
    return _db.client


def get_db() -> AsyncIOMotorDatabase:
    if _db.db is None:
        settings = get_settings()
        _db.db = get_client()[settings.mongo_db]
    return _db.db


def set_db(database: AsyncIOMotorDatabase) -> None:
    """Override the database (used in tests)."""
    _db.db = database


async def close_db() -> None:
    if _db.client is not None:
        _db.client.close()
        _db.client = None
        _db.db = None


async def ensure_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.files.create_index("owner_id")
    await db.files.create_index("created_at")
    await db.chunks.create_index([("file_id", 1), ("chunk_index", 1)])
    await db.chunks.create_index("file_id")
    await db.chats.create_index("owner_id")
