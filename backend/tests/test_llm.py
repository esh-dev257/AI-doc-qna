import pytest

from app.services.llm import LLMClient, _stub_answer, _stub_embedding, _stub_transcription, get_llm, set_llm


@pytest.mark.asyncio
async def test_stub_embedding_is_deterministic_and_normalized():
    a = _stub_embedding("hello world")
    b = _stub_embedding("hello world")
    assert a == b
    # normalized
    mag = sum(x * x for x in a) ** 0.5
    assert abs(mag - 1.0) < 1e-6 or mag == 0.0


@pytest.mark.asyncio
async def test_stub_answer_with_and_without_context():
    assert "offline-mode" in _stub_answer("q", None)
    assert "Based on" in _stub_answer("q", "some context here")


@pytest.mark.asyncio
async def test_llm_client_offline_embed_and_chat():
    client = LLMClient()
    emb = await client.embed(["a", "b"])
    assert len(emb) == 2
    answer = await client.chat("sys", "question", context="ctx")
    assert isinstance(answer, str) and answer


@pytest.mark.asyncio
async def test_llm_client_stream_offline():
    client = LLMClient()
    tokens = []
    async for t in client.stream_chat("sys", "hi", context=None):
        tokens.append(t)
    assert tokens


@pytest.mark.asyncio
async def test_llm_client_summarize_offline():
    client = LLMClient()
    s = await client.summarize("Some long content. " * 100)
    assert isinstance(s, str) and s


@pytest.mark.asyncio
async def test_llm_client_transcribe_stub(tmp_path):
    client = LLMClient()
    p = tmp_path / "fake.mp3"
    p.write_bytes(b"\x00" * 32000)
    result = await client.transcribe(str(p))
    assert "segments" in result
    assert result["segments"]
    assert result["duration"] > 0


def test_set_and_get_llm_singleton():
    class Fake(LLMClient):
        pass

    fake = Fake()
    set_llm(fake)
    assert get_llm() is fake
    # restore
    set_llm(LLMClient())


def test_stub_transcription_missing_file():
    result = _stub_transcription("/no/such/file")
    assert result["duration"] > 0
    assert result["segments"]
