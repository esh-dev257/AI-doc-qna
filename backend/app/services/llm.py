"""Abstraction over chat / embedding / transcription providers.

Supported providers:
  - ``gemini``   Google Generative AI (google-generativeai)
  - ``openai``   OpenAI / OpenAI-compatible API
  - ``offline``  deterministic stub (used when no key is set or for tests)

Selection: ``LLM_PROVIDER`` env var. ``auto`` (default) picks Gemini if
``GEMINI_API_KEY`` is set, else OpenAI if ``OPENAI_API_KEY`` is set, else offline.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import AsyncIterator, Iterable

from app.config import get_settings


class LLMClient:
    def __init__(self, gemini_key: str | None = None, openai_key: str | None = None) -> None:
        self._openai_client = None
        self._gemini_configured = False
        self._genai = None
        # Per-instance overrides. When set, these win over env settings.
        self._gemini_override = gemini_key or None
        self._openai_override = openai_key or None

    def _gemini_key(self) -> str:
        # Only user-supplied keys are ever used. Env keys are ignored by design
        # so the service never spends the operator's credits.
        return self._gemini_override or ""

    def _openai_key(self) -> str:
        return self._openai_override or ""

    # --- provider resolution -------------------------------------------------

    def provider(self) -> str:
        settings = get_settings()
        choice = (settings.llm_provider or "auto").lower()
        if choice == "auto":
            if self._gemini_key():
                return "gemini"
            if self._openai_key():
                return "openai"
            return "offline"
        return choice

    def _openai(self):
        if self._openai_client is not None:
            return self._openai_client
        key = self._openai_key()
        if not key:
            return None
        try:
            from openai import OpenAI
        except Exception:
            return None
        self._openai_client = OpenAI(api_key=key)
        return self._openai_client

    def _gemini(self):
        if self._gemini_configured and self._genai is not None:
            return self._genai
        key = self._gemini_key()
        if not key:
            return None
        try:
            import google.generativeai as genai
        except Exception:
            return None
        genai.configure(api_key=key)
        self._genai = genai
        self._gemini_configured = True
        return genai

    # --- embeddings ----------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        provider = self.provider()
        settings = get_settings()
        if provider == "gemini":
            genai = self._gemini()
            if genai is not None:
                out: list[list[float]] = []
                for t in texts:
                    res = genai.embed_content(
                        model=f"models/{settings.gemini_embed_model}",
                        content=t,
                        task_type="retrieval_document",
                    )
                    out.append(list(res["embedding"]))
                return out
        if provider == "openai":
            client = self._openai()
            if client is not None:
                resp = client.embeddings.create(model=settings.openai_embed_model, input=texts)
                return [d.embedding for d in resp.data]
        return [_stub_embedding(t) for t in texts]

    # --- chat ----------------------------------------------------------------

    async def chat(self, system: str, user: str, context: str | None = None) -> str:
        provider = self.provider()
        settings = get_settings()
        if provider == "gemini":
            genai = self._gemini()
            if genai is not None:
                model = genai.GenerativeModel(
                    settings.gemini_chat_model,
                    system_instruction=system,
                )
                prompt = _compose_user_prompt(user, context)
                resp = model.generate_content(prompt)
                return (getattr(resp, "text", "") or "").strip()
        if provider == "openai":
            client = self._openai()
            if client is not None:
                messages = [{"role": "system", "content": system}]
                if context:
                    messages.append({"role": "system", "content": f"Context:\n{context}"})
                messages.append({"role": "user", "content": user})
                resp = client.chat.completions.create(
                    model=settings.openai_chat_model,
                    messages=messages,
                    temperature=0.2,
                )
                return resp.choices[0].message.content or ""
        return _stub_answer(user, context)

    async def stream_chat(
        self, system: str, user: str, context: str | None = None
    ) -> AsyncIterator[str]:
        provider = self.provider()
        settings = get_settings()

        if provider == "gemini":
            genai = self._gemini()
            if genai is not None:
                model = genai.GenerativeModel(
                    settings.gemini_chat_model,
                    system_instruction=system,
                )
                stream = model.generate_content(_compose_user_prompt(user, context), stream=True)
                for chunk in stream:
                    text = getattr(chunk, "text", None)
                    if text:
                        yield text
                return

        if provider == "openai":
            client = self._openai()
            if client is not None:
                messages = [{"role": "system", "content": system}]
                if context:
                    messages.append({"role": "system", "content": f"Context:\n{context}"})
                messages.append({"role": "user", "content": user})
                stream = client.chat.completions.create(
                    model=settings.openai_chat_model,
                    messages=messages,
                    temperature=0.2,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta
                return

        # offline
        answer = _stub_answer(user, context)
        for word in answer.split(" "):
            yield word + " "

    async def summarize(self, text: str) -> str:
        snippet = text[:12000]
        return await self.chat(
            system=(
                "You produce concise, faithful summaries. "
                "Capture key points, entities, and conclusions in 5-10 sentences."
            ),
            user=f"Summarize the following content:\n\n{snippet}",
        )

    async def generate_diagram(self, text: str) -> str:
        """Produce only a Mermaid flowchart from text. Offline returns a stub."""
        if self.provider() == "offline":
            return _stub_mermaid()
        snippet = text[:8000]
        raw = await self.chat(
            system=(
                "You produce a Mermaid flowchart summarizing the document's flow. "
                "Return ONLY the mermaid source, no markdown fences, no prose. "
                "Start with 'flowchart TD' or 'flowchart LR'. Use simple "
                "A[Label]-->B[Label] syntax. 5-10 nodes maximum."
            ),
            user=f"Document:\n\n{snippet}",
        )
        cleaned = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", (raw or "").strip()).strip()
        if not cleaned.lower().startswith("flowchart"):
            return _stub_mermaid()
        return cleaned

    async def summarize_with_diagram(self, text: str) -> dict:
        """Return {'summary': str, 'mermaid': str} in one LLM call."""
        snippet = text[:12000]
        if self.provider() == "offline":
            return {
                "summary": await self.summarize(text),
                "mermaid": _stub_mermaid(),
            }
        system = (
            "You produce a concise summary AND a Mermaid flow diagram. "
            "Return STRICT JSON (no markdown, no prose) with exactly two fields: "
            '{"summary": "5-10 sentence summary", "mermaid": "flowchart TD\\n..."}\\n'
            "The mermaid field MUST start with 'flowchart TD' or 'flowchart LR' and use "
            "simple square nodes like A[Label] and arrows A-->B. Keep it to 5-10 nodes. "
            "Escape newlines inside the JSON string values."
        )
        raw = await self.chat(system=system, user=f"Document:\n\n{snippet}")
        parsed = _parse_summary_diagram(raw)
        if not parsed.get("summary"):
            parsed["summary"] = await self.summarize(text)
        if not parsed.get("mermaid"):
            parsed["mermaid"] = _stub_mermaid()
        return parsed

    # --- transcription -------------------------------------------------------

    async def transcribe(self, file_path: str) -> dict:
        """Return {'text', 'segments': [{'start','end','text'}], 'duration'}."""
        provider = self.provider()
        settings = get_settings()

        if provider == "gemini":
            genai = self._gemini()
            if genai is not None:
                uploaded = genai.upload_file(path=file_path)
                uploaded = _await_gemini_file_ready(genai, uploaded)
                model = genai.GenerativeModel(settings.gemini_transcribe_model)
                prompt = (
                    "Transcribe this audio/video. Return ONLY a JSON array of "
                    'objects {"start": float_seconds, "end": float_seconds, "text": str}. '
                    "Keep each segment under ~12 seconds. No preamble, no trailing text, "
                    "no markdown fences."
                )
                resp = model.generate_content([uploaded, prompt])
                text = getattr(resp, "text", "") or ""
                segments = _parse_transcript_json(text)
                if not segments:
                    segments = [{"start": 0.0, "end": 0.0, "text": text.strip()}]
                duration = max((float(s.get("end", 0.0)) for s in segments), default=0.0)
                joined = " ".join(s["text"] for s in segments if s.get("text"))
                try:
                    genai.delete_file(uploaded.name)
                except Exception:
                    pass
                return {"text": joined, "segments": segments, "duration": duration}

        if provider == "openai":
            client = self._openai()
            if client is not None:
                with open(file_path, "rb") as fh:
                    resp = client.audio.transcriptions.create(
                        model=settings.openai_transcribe_model,
                        file=fh,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                    )
                data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
                segments = [
                    {"start": float(s["start"]), "end": float(s["end"]), "text": s.get("text", "")}
                    for s in data.get("segments", [])
                ]
                return {
                    "text": data.get("text", ""),
                    "segments": segments,
                    "duration": float(data.get("duration", segments[-1]["end"] if segments else 0.0)),
                }

        return _stub_transcription(file_path)


# --- helpers -----------------------------------------------------------------


def _await_gemini_file_ready(genai, uploaded, timeout: float = 180.0, interval: float = 1.0):
    """Poll a Gemini-uploaded file until it reaches ACTIVE state."""
    import time

    deadline = time.time() + timeout
    current = uploaded
    while True:
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", None) or (str(state) if state is not None else "")
        if state_name == "ACTIVE":
            return current
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {current.name}")
        if time.time() > deadline:
            raise TimeoutError(f"Gemini file {current.name} not ACTIVE after {timeout}s (state={state_name})")
        time.sleep(interval)
        current = genai.get_file(current.name)


def _compose_user_prompt(user: str, context: str | None) -> str:
    if not context:
        return user
    return f"Context:\n{context}\n\nQuestion:\n{user}"


def _parse_transcript_json(text: str) -> list[dict]:
    text = text.strip()
    # Strip markdown fences if present.
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    m = re.search(r"\[[\s\S]*\]", text)
    candidate = m.group(0) if m else text
    try:
        data = json.loads(candidate)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
        except (TypeError, ValueError):
            continue
        txt = str(item.get("text") or "").strip()
        if not txt:
            continue
        cleaned.append({"start": start, "end": end, "text": txt})
    return cleaned


# --- singleton + offline stubs ----------------------------------------------


_llm_singleton: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton


def set_llm(client: LLMClient) -> None:
    """Swap the client (used in tests)."""
    global _llm_singleton
    _llm_singleton = client


EMBED_DIM = 128


def _stub_embedding(text: str) -> list[float]:
    tokens = _tokenize(text)
    vec = [0.0] * EMBED_DIM
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBED_DIM
        sign = 1.0 if (h >> 7) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _tokenize(text: str) -> Iterable[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t]


def _stub_answer(question: str, context: str | None) -> str:
    if context:
        snippet = context[:400].replace("\n", " ")
        return f"Based on the provided content: {snippet}..."
    return f"[offline-mode] You asked: {question}"


def _parse_summary_diagram(raw: str) -> dict:
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    m = re.search(r"\{[\s\S]*\}", text)
    candidate = m.group(0) if m else text
    try:
        data = json.loads(candidate)
    except Exception:
        return {"summary": "", "mermaid": ""}
    if not isinstance(data, dict):
        return {"summary": "", "mermaid": ""}
    summary = str(data.get("summary") or "").strip()
    mermaid = str(data.get("mermaid") or "").strip()
    # Defensive: strip any leftover fences inside the mermaid string.
    mermaid = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", mermaid).strip()
    return {"summary": summary, "mermaid": mermaid}


def _stub_mermaid() -> str:
    return (
        "flowchart TD\n"
        "    A[Upload file] --> B[Extract text]\n"
        "    B --> C[Chunk & embed]\n"
        "    C --> D[Summarize]\n"
        "    D --> E[Ready to chat]"
    )


def _stub_transcription(file_path: str) -> dict:
    import os

    size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    duration = max(1.0, size / 16000.0)
    seg_count = max(1, int(duration // 5))
    seg_len = duration / seg_count
    segments = [
        {
            "start": i * seg_len,
            "end": (i + 1) * seg_len,
            "text": f"Transcript segment {i + 1} of stub audio.",
        }
        for i in range(seg_count)
    ]
    return {
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "duration": duration,
    }
