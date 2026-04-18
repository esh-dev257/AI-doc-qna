"""Ingestion pipeline: turn an uploaded file into searchable chunks + summary."""
from __future__ import annotations

import asyncio
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
from app.services.llm import LLMClient, get_llm


async def ingest_file(
    file_id: str,
    file_path: str,
    kind: str,
    api_keys: dict | None = None,
) -> dict:
    db = get_db()
    if api_keys and (api_keys.get("gemini") or api_keys.get("openai")):
        llm = LLMClient(
            gemini_key=api_keys.get("gemini"),
            openai_key=api_keys.get("openai"),
        )
    else:
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

        # Run embedding and summary concurrently — they don't depend on each
        # other. Saves ~2-5s depending on document size.
        embed_coro = llm.embed([c.text for c in chunks])
        summary_coro = llm.summarize(full_text) if full_text else _noop_summary()
        embeddings, summary = await asyncio.gather(embed_coro, summary_coro)

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


async def _noop_summary() -> str:
    return ""


def delete_file_blob(file_path: str) -> None:
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass
