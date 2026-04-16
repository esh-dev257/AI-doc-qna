"""Ingestion pipeline: turn an uploaded file into searchable chunks + summary."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

from app.database import get_db
from app.services.extraction import (
    ExtractedChunk,
    chunk_text,
    chunks_from_segments,
    extract_pdf_text,
)
from app.services.llm import get_llm


async def ingest_file(file_id: str, file_path: str, kind: str) -> dict:
    db = get_db()
    llm = get_llm()

    await db.files.update_one({"_id": ObjectId(file_id)}, {"$set": {"status": "processing"}})

    try:
        full_text = ""
        chunks: list[ExtractedChunk] = []
        duration: float | None = None

        if kind == "pdf":
            with open(file_path, "rb") as fh:
                data = fh.read()
            full_text = extract_pdf_text(data)
            plain = chunk_text(full_text)
            chunks = [ExtractedChunk(text=t, chunk_index=i) for i, t in enumerate(plain)]
        else:
            result = await llm.transcribe(file_path)
            full_text = result.get("text", "")
            duration = result.get("duration")
            segs = result.get("segments", [])
            chunks = chunks_from_segments(segs)
            if not chunks and full_text:
                plain = chunk_text(full_text)
                chunks = [ExtractedChunk(text=t, chunk_index=i) for i, t in enumerate(plain)]

        if not chunks:
            raise ValueError("No text extracted from file")

        embeddings = await llm.embed([c.text for c in chunks])

        chunk_docs = []
        for c, emb in zip(chunks, embeddings):
            chunk_docs.append(
                {
                    "file_id": file_id,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "embedding": emb,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        await db.chunks.insert_many(chunk_docs)

        summary = await llm.summarize(full_text) if full_text else ""

        await db.files.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$set": {
                    "status": "ready",
                    "summary": summary,
                    "full_text_length": len(full_text),
                    "duration_seconds": duration,
                    "chunk_count": len(chunk_docs),
                    "processed_at": datetime.now(timezone.utc),
                }
            },
        )
        return {"status": "ready", "chunks": len(chunk_docs), "summary": summary}
    except Exception as exc:  # noqa: BLE001
        await db.files.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"status": "failed", "error": str(exc)}},
        )
        raise


def delete_file_blob(file_path: str) -> None:
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass
