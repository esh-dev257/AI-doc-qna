"""Simple in-Mongo vector store with cosine similarity.

Embeddings are persisted alongside chunks in the `chunks` collection.
Search is done in Python for portability; for production you'd swap to
MongoDB Atlas Vector Search or FAISS with a persisted index.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.database import get_db


@dataclass
class VectorHit:
    chunk_id: str
    file_id: str
    chunk_index: int
    text: str
    score: float
    start_time: float | None
    end_time: float | None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def search(file_id: str, query_embedding: list[float], top_k: int = 4) -> list[VectorHit]:
    db = get_db()
    cursor = db.chunks.find({"file_id": file_id})
    hits: list[VectorHit] = []
    async for doc in cursor:
        emb = doc.get("embedding") or []
        score = cosine(query_embedding, emb)
        hits.append(
            VectorHit(
                chunk_id=str(doc["_id"]),
                file_id=str(doc["file_id"]),
                chunk_index=int(doc.get("chunk_index", 0)),
                text=doc.get("text", ""),
                score=score,
                start_time=doc.get("start_time"),
                end_time=doc.get("end_time"),
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
