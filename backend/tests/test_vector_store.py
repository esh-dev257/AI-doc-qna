import pytest

from app.services import vector_store
from app.services.vector_store import cosine, search


def test_cosine_basics():
    assert cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([], [1]) == 0.0
    assert cosine([0, 0], [0, 0]) == 0.0
    assert cosine([1, 2, 3], [1, 2]) == 0.0


@pytest.mark.asyncio
async def test_search_returns_top_k(db):
    await db.chunks.insert_many(
        [
            {"file_id": "f1", "chunk_index": 0, "text": "a", "embedding": [1.0, 0.0]},
            {"file_id": "f1", "chunk_index": 1, "text": "b", "embedding": [0.9, 0.1]},
            {"file_id": "f1", "chunk_index": 2, "text": "c", "embedding": [0.0, 1.0]},
            {"file_id": "f2", "chunk_index": 0, "text": "other", "embedding": [1.0, 0.0]},
        ]
    )
    hits = await search("f1", [1.0, 0.0], top_k=2)
    assert len(hits) == 2
    assert hits[0].text == "a"
    assert hits[1].text == "b"
    for h in hits:
        assert h.file_id == "f1"
