import asyncio
import io

import pytest

from app.services.ingestion import ingest_file


async def _wait_ready(client, file_id: str, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        r = await client.get(f"/api/files/{file_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] in ("ready", "failed"):
            return data
        if asyncio.get_event_loop().time() > deadline:
            return data
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_upload_pdf_ingest_chat_and_summary(auth_client, real_pdf_bytes):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("doc.pdf", real_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    file_id = r.json()["id"]

    data = await _wait_ready(auth_client, file_id)
    assert data["status"] == "ready"

    # list
    lst = await auth_client.get("/api/files")
    assert lst.status_code == 200
    assert any(f["id"] == file_id for f in lst.json())

    # summary
    s = await auth_client.get(f"/api/files/{file_id}/summary")
    assert s.status_code == 200
    assert s.json()["file_id"] == file_id

    # chat
    chat = await auth_client.post(
        "/api/chat",
        json={"file_id": file_id, "question": "What is this about?", "top_k": 2},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "answer" in body
    assert isinstance(body["citations"], list)

    # chat from cache (second call)
    chat2 = await auth_client.post(
        "/api/chat",
        json={"file_id": file_id, "question": "What is this about?", "top_k": 2},
    )
    assert chat2.status_code == 200

    # timestamps not allowed for pdf
    ts = await auth_client.post(
        "/api/chat/timestamps",
        json={"file_id": file_id, "topic": "anything"},
    )
    assert ts.status_code == 400

    # stream endpoint returns SSE
    async with auth_client.stream(
        "POST",
        "/api/chat/stream",
        json={"file_id": file_id, "question": "summary please"},
    ) as resp:
        assert resp.status_code == 200
        seen_tokens = False
        seen_citations = False
        async for line in resp.aiter_lines():
            if line.startswith("event: token"):
                seen_tokens = True
            if line.startswith("event: citations"):
                seen_citations = True
        assert seen_tokens
        assert seen_citations


@pytest.mark.asyncio
async def test_upload_audio_transcribe_and_timestamps(auth_client, tmp_path):
    audio = b"\x00" * 48000
    r = await auth_client.post(
        "/api/files",
        files={"file": ("clip.mp3", audio, "audio/mpeg")},
    )
    assert r.status_code == 201
    file_id = r.json()["id"]
    data = await _wait_ready(auth_client, file_id)
    assert data["status"] == "ready"
    assert data["duration_seconds"] and data["duration_seconds"] > 0

    ts = await auth_client.post(
        "/api/chat/timestamps",
        json={"file_id": file_id, "topic": "segment", "top_k": 3},
    )
    assert ts.status_code == 200
    hits = ts.json()["hits"]
    assert hits
    for h in hits:
        assert h["start_time"] is not None
        assert h["end_time"] is not None


@pytest.mark.asyncio
async def test_upload_unsupported_type(auth_client):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("bad.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_empty(auth_client):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_too_large(auth_client, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    r = await auth_client.post(
        "/api/files",
        files={"file": ("big.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    assert r.status_code == 413
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_file_not_found(auth_client):
    r = await auth_client.get("/api/files/000000000000000000000000")
    assert r.status_code == 404
    r2 = await auth_client.get("/api/files/not-an-id")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_summary_not_found(auth_client):
    r = await auth_client.get("/api/files/000000000000000000000000/summary")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_media_stream_and_delete(auth_client, real_pdf_bytes):
    r = await auth_client.post(
        "/api/files",
        files={"file": ("doc.pdf", real_pdf_bytes, "application/pdf")},
    )
    file_id = r.json()["id"]
    await _wait_ready(auth_client, file_id)

    media = await auth_client.get(f"/api/files/{file_id}/media")
    assert media.status_code == 200
    assert media.content[:4] == b"%PDF"

    # delete
    d = await auth_client.delete(f"/api/files/{file_id}")
    assert d.status_code == 204

    # second delete -> 404
    d2 = await auth_client.delete(f"/api/files/{file_id}")
    assert d2.status_code == 404


@pytest.mark.asyncio
async def test_media_stream_missing(auth_client):
    r = await auth_client.get("/api/files/000000000000000000000000/media")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_chat_file_not_ready(auth_client, db):
    from bson import ObjectId
    from datetime import datetime, timezone

    res = await db.files.insert_one(
        {
            "owner_id": (await auth_client.get("/api/auth/me")).json()["id"],
            "filename": "x.pdf",
            "kind": "pdf",
            "status": "processing",
            "size_bytes": 10,
            "created_at": datetime.now(timezone.utc),
        }
    )
    r = await auth_client.post(
        "/api/chat",
        json={"file_id": str(res.inserted_id), "question": "hi"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_chat_file_missing(auth_client):
    r = await auth_client.post(
        "/api/chat",
        json={"file_id": "000000000000000000000000", "question": "hi"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ingest_failure_marks_failed(auth_client, db, monkeypatch):
    # Upload a pdf where extraction returns no text -> ingestion raises
    from app.services import extraction

    def fake_extract(_b):
        return ""

    monkeypatch.setattr(extraction, "extract_pdf_text", fake_extract)
    from app.services import ingestion

    monkeypatch.setattr(ingestion, "extract_pdf_text", fake_extract)

    r = await auth_client.post(
        "/api/files",
        files={"file": ("doc.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    file_id = r.json()["id"]
    data = await _wait_ready(auth_client, file_id)
    assert data["status"] == "failed"
    assert data["error"]
