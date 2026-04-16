import asyncio
import io
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

os.environ.setdefault("MONGO_URI", "mongodb://mock")
os.environ.setdefault("MONGO_DB", "test_ai_qa")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("REDIS_ENABLED", "false")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db():
    from app import database

    client = AsyncMongoMockClient()
    mock_db = client["test_ai_qa"]
    database._db.client = client
    database._db.db = mock_db
    await database.ensure_indexes()
    yield mock_db
    database._db.client = None
    database._db.db = None


@pytest_asyncio.fixture
async def tmp_upload(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(db, tmp_upload):
    from app.main import create_app
    from app.services import rate_limit

    rate_limit.reset()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "hunter2!"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, create_string_object

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({"/Title": "Sample"})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def real_pdf_bytes() -> bytes:
    """A minimal PDF with actual extractable text using reportlab-free approach."""
    # Hand-rolled minimal PDF containing the phrase "Hello World from Panscience".
    content = (
        "%PDF-1.4\n"
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        "/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        "4 0 obj<</Length 84>>stream\n"
        "BT /F1 18 Tf 72 720 Td (Hello World from Panscience Assignment text.) Tj ET\n"
        "endstream endobj\n"
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        "xref\n0 6\n"
        "0000000000 65535 f \n"
        "0000000010 00000 n \n"
        "0000000053 00000 n \n"
        "0000000098 00000 n \n"
        "0000000181 00000 n \n"
        "0000000289 00000 n \n"
        "trailer<</Size 6/Root 1 0 R>>\nstartxref\n350\n%%EOF\n"
    )
    return content.encode("latin-1")
