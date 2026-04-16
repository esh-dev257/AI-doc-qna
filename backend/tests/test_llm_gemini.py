"""Tests for the Gemini branches of LLMClient using mocks."""
from __future__ import annotations

import types

import pytest

from app.config import get_settings
from app.services import llm as llm_mod


class _FakeGenResponse:
    def __init__(self, text):
        self.text = text


class _FakeChunk:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def __init__(self, name, system_instruction=None):
        self.name = name
        self.system_instruction = system_instruction

    def generate_content(self, prompt, stream=False):
        if isinstance(prompt, list):
            return _FakeGenResponse(
                '[{"start": 0.0, "end": 1.5, "text": "hello"},'
                ' {"start": 1.5, "end": 3.0, "text": "world"}]'
            )
        if stream:
            return iter([_FakeChunk("gem-"), _FakeChunk("ini "), _FakeChunk(None), _FakeChunk("ok")])
        return _FakeGenResponse("gemini answer")


class _FakeGenAI:
    def __init__(self):
        self.configured_with = None

    def configure(self, api_key):
        self.configured_with = api_key

    def embed_content(self, model, content, task_type):
        return {"embedding": [0.11, 0.22, 0.33]}

    def GenerativeModel(self, name, system_instruction=None):
        return _FakeModel(name, system_instruction=system_instruction)

    def upload_file(self, path):
        return types.SimpleNamespace(path=path)


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def patched_genai(monkeypatch, gemini_env):
    """Inject a fake google.generativeai module via sys.modules."""
    import sys

    fake = _FakeGenAI()
    # Pretend the package is already imported.
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    # And that `google` has `.generativeai`.
    google_mod = sys.modules.get("google")
    if google_mod is None:
        google_mod = types.ModuleType("google")
        monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setattr(google_mod, "generativeai", fake, raising=False)
    yield fake


@pytest.mark.asyncio
async def test_provider_auto_picks_gemini(gemini_env):
    assert llm_mod.LLMClient().provider() == "gemini"


@pytest.mark.asyncio
async def test_provider_explicit_offline(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    monkeypatch.setenv("GEMINI_API_KEY", "whatever")
    get_settings.cache_clear()
    assert llm_mod.LLMClient().provider() == "offline"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_provider_explicit_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    assert llm_mod.LLMClient().provider() == "openai"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_gemini_embed(patched_genai):
    client = llm_mod.LLMClient()
    out = await client.embed(["a", "b"])
    assert out == [[0.11, 0.22, 0.33], [0.11, 0.22, 0.33]]
    assert patched_genai.configured_with == "gm-test"


@pytest.mark.asyncio
async def test_gemini_chat(patched_genai):
    client = llm_mod.LLMClient()
    text = await client.chat("sys", "q", context="c")
    assert text == "gemini answer"


@pytest.mark.asyncio
async def test_gemini_stream(patched_genai):
    client = llm_mod.LLMClient()
    collected = []
    async for t in client.stream_chat("sys", "q", context="c"):
        collected.append(t)
    assert collected == ["gem-", "ini ", "ok"]


@pytest.mark.asyncio
async def test_gemini_transcribe(patched_genai, tmp_path):
    client = llm_mod.LLMClient()
    f = tmp_path / "x.mp3"
    f.write_bytes(b"\x00" * 100)
    res = await client.transcribe(str(f))
    assert res["duration"] == 3.0
    assert len(res["segments"]) == 2
    assert res["segments"][0] == {"start": 0.0, "end": 1.5, "text": "hello"}
    assert "hello" in res["text"]


@pytest.mark.asyncio
async def test_gemini_transcribe_invalid_json_falls_back(monkeypatch, gemini_env, tmp_path):
    import sys

    class BadModel:
        def generate_content(self, *a, **kw):
            return _FakeGenResponse("not json at all")

    class BadGenAI(_FakeGenAI):
        def GenerativeModel(self, name, system_instruction=None):
            return BadModel()

    fake = BadGenAI()
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setattr(google_mod, "generativeai", fake, raising=False)

    client = llm_mod.LLMClient()
    f = tmp_path / "x.mp3"
    f.write_bytes(b"\x00")
    res = await client.transcribe(str(f))
    assert res["segments"][0]["text"] == "not json at all"


@pytest.mark.asyncio
async def test_gemini_import_failure_falls_back(monkeypatch, gemini_env):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "google.generativeai" or (
            name.startswith("google") and len(a) >= 3 and "generativeai" in (a[2] or ())
        ):
            raise ImportError("nope")
        return real_import(name, *a, **kw)

    # Ensure a cached module won't satisfy the import.
    import sys

    monkeypatch.delitem(sys.modules, "google.generativeai", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = llm_mod.LLMClient()
    # falls back to offline stub
    out = await client.embed(["a"])
    assert len(out) == 1 and len(out[0]) == llm_mod.EMBED_DIM


def test_parse_transcript_strips_fences():
    text = "```json\n[{\"start\": 0.0, \"end\": 1.0, \"text\": \"hi\"}]\n```"
    out = llm_mod._parse_transcript_json(text)
    assert out == [{"start": 0.0, "end": 1.0, "text": "hi"}]


def test_parse_transcript_rejects_non_list():
    assert llm_mod._parse_transcript_json('{"a": 1}') == []


def test_parse_transcript_skips_bad_items():
    text = '[{"start": "x", "end": 1, "text": "ok"}, {"text": ""}, {"start": 0, "end": 1, "text": "fine"}]'
    out = llm_mod._parse_transcript_json(text)
    assert out == [{"start": 0.0, "end": 1.0, "text": "fine"}]


def test_parse_transcript_unparseable():
    assert llm_mod._parse_transcript_json("no json here") == []
