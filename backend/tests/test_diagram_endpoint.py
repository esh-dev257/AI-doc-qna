import pytest
from bson import ObjectId

from app.database import get_db
from app.services.llm import LLMClient


@pytest.mark.asyncio
async def test_generate_diagram_offline_returns_stub():
    client = LLMClient()
    out = await client.generate_diagram("some document text")
    assert out.startswith("flowchart TD")


@pytest.mark.asyncio
async def test_generate_diagram_non_offline_returns_llm_output(monkeypatch):
    client = LLMClient(openai_key="sk-fake")
    assert client.provider() == "openai"

    async def fake_chat(self, system, user, context=None):
        return "flowchart TD\n  A[Start]-->B[End]"

    monkeypatch.setattr(LLMClient, "chat", fake_chat, raising=True)
    out = await client.generate_diagram("content")
    assert out.startswith("flowchart TD")
    assert "A[Start]" in out


@pytest.mark.asyncio
async def test_generate_diagram_falls_back_on_invalid_output(monkeypatch):
    client = LLMClient(gemini_key="g-fake")
    assert client.provider() == "gemini"

    async def bad(self, system, user, context=None):
        return "sorry, not a diagram"

    monkeypatch.setattr(LLMClient, "chat", bad, raising=True)
    out = await client.generate_diagram("content")
    assert out.startswith("flowchart TD")  # stub


@pytest.mark.asyncio
async def test_generate_diagram_strips_markdown_fence(monkeypatch):
    client = LLMClient(openai_key="sk")
    assert client.provider() == "openai"

    async def fenced(self, system, user, context=None):
        return "```mermaid\nflowchart LR\n A-->B\n```"

    monkeypatch.setattr(LLMClient, "chat", fenced, raising=True)
    out = await client.generate_diagram("x")
    assert out.startswith("flowchart LR")
    assert "```" not in out


@pytest.mark.asyncio
async def test_diagram_endpoint_generates_and_caches(auth_client, sample_pdf_bytes):
    # Upload (sync ingest path using stubs)
    r = await auth_client.post(
        "/api/files",
        files={"file": ("doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 201
    fid = r.json()["id"]

    # Force the file to a ready state with a summary present.
    db = get_db()
    await db.files.update_one(
        {"_id": ObjectId(fid)},
        {"$set": {"status": "ready", "summary": "Brief summary."}},
    )

    # First call generates diagram.
    r1 = await auth_client.post(f"/api/files/{fid}/summary/diagram")
    assert r1.status_code == 200, r1.text
    diagram = r1.json()["diagram"]
    assert diagram.startswith("flowchart TD")

    # Cached in DB.
    doc = await db.files.find_one({"_id": ObjectId(fid)})
    assert doc["summary_diagram"] == diagram

    # Second call returns the cached diagram without regenerating.
    r2 = await auth_client.post(f"/api/files/{fid}/summary/diagram")
    assert r2.status_code == 200
    assert r2.json()["diagram"] == diagram


@pytest.mark.asyncio
async def test_diagram_endpoint_404_for_missing_file(auth_client):
    r = await auth_client.post(f"/api/files/{ObjectId()}/summary/diagram")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_diagram_endpoint_409_when_not_ready(auth_client, sample_pdf_bytes):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("d.pdf", sample_pdf_bytes, "application/pdf")},
    )
    fid = r.json()["id"]
    db = get_db()
    await db.files.update_one(
        {"_id": ObjectId(fid)},
        {"$set": {"status": "processing"}, "$unset": {"summary": ""}},
    )
    r2 = await auth_client.post(f"/api/files/{fid}/summary/diagram")
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_diagram_endpoint_uses_chunks_when_no_summary(auth_client, sample_pdf_bytes):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("d.pdf", sample_pdf_bytes, "application/pdf")},
    )
    fid = r.json()["id"]
    db = get_db()
    await db.files.update_one(
        {"_id": ObjectId(fid)},
        {"$set": {"status": "ready"}, "$unset": {"summary": "", "summary_diagram": ""}},
    )
    # Inject a chunk so the "no summary" branch has something to work with.
    await db.chunks.insert_one(
        {
            "file_id": fid,
            "chunk_index": 0,
            "text": "a lone chunk",
            "start_time": None,
            "end_time": None,
            "embedding": [0.0],
        }
    )
    r2 = await auth_client.post(f"/api/files/{fid}/summary/diagram")
    assert r2.status_code == 200
    assert r2.json()["diagram"].startswith("flowchart TD")


@pytest.mark.asyncio
async def test_diagram_endpoint_400_when_no_content(auth_client, sample_pdf_bytes):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("d.pdf", sample_pdf_bytes, "application/pdf")},
    )
    fid = r.json()["id"]
    db = get_db()
    await db.files.update_one(
        {"_id": ObjectId(fid)},
        {"$set": {"status": "ready"}, "$unset": {"summary": "", "summary_diagram": ""}},
    )
    await db.chunks.delete_many({"file_id": fid})
    r2 = await auth_client.post(f"/api/files/{fid}/summary/diagram")
    assert r2.status_code == 400
