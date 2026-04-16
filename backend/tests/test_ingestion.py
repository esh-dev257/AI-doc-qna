import pytest
from bson import ObjectId
from datetime import datetime, timezone

from app.services.ingestion import delete_file_blob, ingest_file


@pytest.mark.asyncio
async def test_ingest_pdf_inserts_chunks(db, tmp_path, real_pdf_bytes):
    res = await db.files.insert_one(
        {
            "owner_id": "u1",
            "filename": "x.pdf",
            "kind": "pdf",
            "status": "pending",
            "size_bytes": len(real_pdf_bytes),
            "created_at": datetime.now(timezone.utc),
        }
    )
    p = tmp_path / "x.pdf"
    p.write_bytes(real_pdf_bytes)
    result = await ingest_file(str(res.inserted_id), str(p), "pdf")
    assert result["status"] == "ready"
    # file marked ready
    doc = await db.files.find_one({"_id": res.inserted_id})
    assert doc["status"] == "ready"
    # chunks inserted
    count = await db.chunks.count_documents({"file_id": str(res.inserted_id)})
    assert count >= 1


@pytest.mark.asyncio
async def test_ingest_audio_generates_timestamps(db, tmp_path):
    res = await db.files.insert_one(
        {
            "owner_id": "u1",
            "filename": "a.mp3",
            "kind": "audio",
            "status": "pending",
            "size_bytes": 16000,
            "created_at": datetime.now(timezone.utc),
        }
    )
    p = tmp_path / "a.mp3"
    p.write_bytes(b"\x00" * 32000)
    result = await ingest_file(str(res.inserted_id), str(p), "audio")
    assert result["status"] == "ready"
    chunks = [c async for c in db.chunks.find({"file_id": str(res.inserted_id)})]
    assert chunks
    assert any(c.get("start_time") is not None for c in chunks)


@pytest.mark.asyncio
async def test_ingest_failure_no_chunks(db, tmp_path, monkeypatch):
    from app.services import ingestion

    monkeypatch.setattr(ingestion, "extract_pdf_text", lambda _b: "")
    res = await db.files.insert_one(
        {
            "owner_id": "u1",
            "filename": "empty.pdf",
            "kind": "pdf",
            "status": "pending",
            "size_bytes": 0,
            "created_at": datetime.now(timezone.utc),
        }
    )
    p = tmp_path / "empty.pdf"
    p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pytest.raises(Exception):
        await ingest_file(str(res.inserted_id), str(p), "pdf")
    doc = await db.files.find_one({"_id": res.inserted_id})
    assert doc["status"] == "failed"


def test_delete_file_blob_missing_ok(tmp_path):
    delete_file_blob(str(tmp_path / "no-such-file"))


def test_delete_file_blob_existing(tmp_path):
    p = tmp_path / "exists.bin"
    p.write_bytes(b"hi")
    delete_file_blob(str(p))
    assert not p.exists()
