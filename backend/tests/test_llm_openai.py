"""Tests for the OpenAI-enabled branches of LLMClient using mocks."""
from __future__ import annotations

import types

import pytest

from app.services import llm as llm_mod


class _FakeCompletion:
    def __init__(self, text: str):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=text))]


class _FakeStreamChunk:
    def __init__(self, text: str | None):
        self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=text))]


class _FakeEmbeddings:
    def create(self, model, input):
        return types.SimpleNamespace(
            data=[types.SimpleNamespace(embedding=[0.1, 0.2, 0.3]) for _ in input]
        )


class _FakeChatCompletions:
    def __init__(self, *, stream_chunks=None, text="mocked answer"):
        self._stream_chunks = stream_chunks or [_FakeStreamChunk("hel"), _FakeStreamChunk("lo"), _FakeStreamChunk(None)]
        self._text = text

    def create(self, model, messages, temperature, stream=False):
        if stream:
            return iter(self._stream_chunks)
        return _FakeCompletion(self._text)


class _FakeAudio:
    class transcriptions:
        @staticmethod
        def create(model, file, response_format, timestamp_granularities):
            obj = types.SimpleNamespace(
                text="hi there",
                segments=[{"start": 0.0, "end": 1.0, "text": "hi there"}],
                duration=1.0,
            )
            obj.model_dump = lambda: {
                "text": "hi there",
                "segments": [{"start": 0.0, "end": 1.0, "text": "hi there"}],
                "duration": 1.0,
            }
            return obj


class FakeOpenAIClient:
    def __init__(self):
        self.embeddings = _FakeEmbeddings()
        self.chat = types.SimpleNamespace(completions=_FakeChatCompletions())
        self.audio = _FakeAudio()


@pytest.fixture
def openai_client(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    fake = FakeOpenAIClient()
    client = llm_mod.LLMClient(openai_key="sk-test")
    client._openai_client = fake
    yield client
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_openai_embed(openai_client):
    out = await openai_client.embed(["a", "b"])
    assert out == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_openai_chat(openai_client):
    text = await openai_client.chat("sys", "q", context="c")
    assert text == "mocked answer"


@pytest.mark.asyncio
async def test_openai_stream_chat(openai_client):
    tokens = []
    async for t in openai_client.stream_chat("sys", "q", context="c"):
        tokens.append(t)
    assert tokens == ["hel", "lo"]


@pytest.mark.asyncio
async def test_openai_transcribe(openai_client, tmp_path):
    p = tmp_path / "a.mp3"
    p.write_bytes(b"\x00" * 100)
    res = await openai_client.transcribe(str(p))
    assert res["text"] == "hi there"
    assert res["duration"] == 1.0


@pytest.mark.asyncio
async def test_openai_client_creation_no_key():
    # No override key + env ignored -> no client.
    client = llm_mod.LLMClient()
    assert client._openai() is None


@pytest.mark.asyncio
async def test_openai_client_creation_with_key(monkeypatch):
    created = {}

    class FakeOpenAI:
        def __init__(self, api_key):
            created["api_key"] = api_key
            self.ok = True

    import openai as openai_module

    monkeypatch.setattr(openai_module, "OpenAI", FakeOpenAI, raising=False)
    client = llm_mod.LLMClient(openai_key="sk-test")
    c = client._openai()
    assert c is not None and getattr(c, "ok", False)
    assert created["api_key"] == "sk-test"
    # caches instance
    assert client._openai() is c


@pytest.mark.asyncio
async def test_openai_import_failure(monkeypatch):
    import builtins

    orig_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    client = llm_mod.LLMClient(openai_key="sk-test")
    assert client._openai() is None


@pytest.mark.asyncio
async def test_openai_chat_returns_empty_when_none(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()

    client = llm_mod.LLMClient(openai_key="sk-test")

    class NoneContent:
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=None))]

    class Completions:
        def create(self, **kwargs):
            return NoneContent()

    client._openai_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=Completions())
    )
    assert await client.chat("sys", "q") == ""
    get_settings.cache_clear()
