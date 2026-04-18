import pytest

from app.services import llm as llm_module
from app.services.llm import LLMClient, _parse_summary_diagram


@pytest.mark.asyncio
async def test_summarize_with_diagram_offline_uses_stub_mermaid():
    client = LLMClient()
    result = await client.summarize_with_diagram("a long document. " * 50)
    assert isinstance(result, dict)
    assert result["summary"]
    assert result["mermaid"].startswith("flowchart TD")


@pytest.mark.asyncio
async def test_summarize_with_diagram_parses_llm_json(monkeypatch):
    client = LLMClient(openai_key="sk-fake")  # force non-offline provider
    assert client.provider() == "openai"

    async def fake_chat(self, system, user, context=None):
        return (
            '{"summary": "Doc describes X.", '
            '"mermaid": "flowchart TD\\n  A[Start]-->B[End]"}'
        )

    monkeypatch.setattr(LLMClient, "chat", fake_chat, raising=True)
    out = await client.summarize_with_diagram("content")
    assert out["summary"].startswith("Doc describes")
    assert "flowchart TD" in out["mermaid"]


@pytest.mark.asyncio
async def test_summarize_with_diagram_falls_back_when_llm_returns_garbage(monkeypatch):
    client = LLMClient(gemini_key="fake")
    assert client.provider() == "gemini"

    async def bad_chat(self, system, user, context=None):
        return "not json at all"

    async def fake_summary(self, text):
        return "plain summary"

    monkeypatch.setattr(LLMClient, "chat", bad_chat, raising=True)
    monkeypatch.setattr(LLMClient, "summarize", fake_summary, raising=True)
    out = await client.summarize_with_diagram("content")
    assert out["summary"] == "plain summary"
    assert out["mermaid"].startswith("flowchart TD")


def test_parse_summary_diagram_strips_fences_and_extra_text():
    raw = '```json\n{"summary": "s", "mermaid": "flowchart TD\\n  A-->B"}\n```'
    parsed = _parse_summary_diagram(raw)
    assert parsed["summary"] == "s"
    assert parsed["mermaid"].startswith("flowchart TD")


def test_parse_summary_diagram_returns_empty_on_bad_json():
    parsed = _parse_summary_diagram("totally not json")
    assert parsed == {"summary": "", "mermaid": ""}


def test_llm_client_provider_prefers_override_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    assert LLMClient().provider() == "offline"
    assert LLMClient(openai_key="o").provider() == "openai"
    assert LLMClient(gemini_key="g").provider() == "gemini"

    get_settings.cache_clear()


def test_stub_mermaid_is_valid_flowchart():
    out = llm_module._stub_mermaid()
    assert out.startswith("flowchart TD")
    assert "-->" in out
