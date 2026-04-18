import pytest

from app.deps import api_keys_from_headers, get_llm_for_request
from app.services.llm import LLMClient, get_llm, set_llm


def test_api_keys_from_headers_strips_and_returns_none_for_blank():
    out = api_keys_from_headers(x_gemini_api_key="  ", x_openai_api_key=None)
    assert out == {"gemini": None, "openai": None}


def test_api_keys_from_headers_preserves_values():
    out = api_keys_from_headers(x_gemini_api_key="g-1", x_openai_api_key="sk-2")
    assert out == {"gemini": "g-1", "openai": "sk-2"}


def test_get_llm_for_request_returns_singleton_without_headers():
    singleton = LLMClient()
    set_llm(singleton)
    result = get_llm_for_request({"gemini": None, "openai": None})
    assert result is get_llm()


def test_get_llm_for_request_builds_new_client_with_keys():
    set_llm(LLMClient())
    result = get_llm_for_request({"gemini": "g", "openai": None})
    assert result is not get_llm()
    assert result.provider() == "gemini"


@pytest.mark.asyncio
async def test_upload_header_keys_reach_ingestion(monkeypatch, auth_client, sample_pdf_bytes):
    # Capture the api_keys that reach ingest_file via the background task.
    seen: dict = {}

    async def fake_ingest(file_id, file_path, kind, api_keys=None):
        seen["keys"] = api_keys
        from bson import ObjectId

        from app.database import get_db

        await get_db().files.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"status": "ready", "summary": "ok", "summary_diagram": "flowchart TD\n A-->B"}},
        )

    monkeypatch.setattr("app.routers.files.ingest_file", fake_ingest)

    r = await auth_client.post(
        "/api/files",
        files={"file": ("doc.pdf", sample_pdf_bytes, "application/pdf")},
        headers={"X-Gemini-Api-Key": "g-key", "X-OpenAI-Api-Key": "sk-key"},
    )
    assert r.status_code == 201, r.text
    # Background task runs synchronously in tests via BackgroundTasks + ASGITransport.
    assert seen["keys"] == {"gemini": "g-key", "openai": "sk-key"}
