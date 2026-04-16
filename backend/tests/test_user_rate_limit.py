import pytest

from app.services import rate_limit


@pytest.mark.asyncio
async def test_user_rate_limit_blocks(auth_client, monkeypatch, real_pdf_bytes):
    # upload a pdf and wait for ready
    r = await auth_client.post(
        "/api/files",
        files={"file": ("d.pdf", real_pdf_bytes, "application/pdf")},
    )
    file_id = r.json()["id"]
    # wait
    import asyncio

    for _ in range(40):
        s = await auth_client.get(f"/api/files/{file_id}")
        if s.json()["status"] == "ready":
            break
        await asyncio.sleep(0.05)

    # monkeypatch check_rate_limit to deny
    def deny(key, limit=None, window=60):
        return False

    from app import deps

    monkeypatch.setattr(deps, "check_rate_limit", deny)

    r = await auth_client.post(
        "/api/chat",
        json={"file_id": file_id, "question": "q?"},
    )
    assert r.status_code == 429
    rate_limit.reset()
