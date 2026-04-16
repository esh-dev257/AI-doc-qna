"""Text extraction for PDFs and media transcription."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ExtractedChunk:
    text: str
    chunk_index: int
    start_time: float | None = None
    end_time: float | None = None


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        parts.append(text)
    return "\n\n".join(parts).strip()


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks by character count, preferring sentence boundaries."""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = text[start:end]
            m = max(window.rfind(". "), window.rfind("\n"), window.rfind("? "), window.rfind("! "))
            if m > chunk_size * 0.5:
                end = start + m + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def chunks_from_segments(
    segments: list[dict], target_chars: int = 800
) -> list[ExtractedChunk]:
    """Group transcript segments into chunks with start/end timestamps."""
    chunks: list[ExtractedChunk] = []
    buf: list[str] = []
    buf_start: float | None = None
    buf_end: float | None = None
    char_count = 0
    idx = 0
    for seg in segments:
        seg_text = (seg.get("text") or "").strip()
        if not seg_text:
            continue
        if buf_start is None:
            buf_start = float(seg.get("start", 0.0))
        buf_end = float(seg.get("end", buf_start))
        buf.append(seg_text)
        char_count += len(seg_text) + 1
        if char_count >= target_chars:
            chunks.append(
                ExtractedChunk(
                    text=" ".join(buf).strip(),
                    chunk_index=idx,
                    start_time=buf_start,
                    end_time=buf_end,
                )
            )
            idx += 1
            buf, buf_start, buf_end, char_count = [], None, None, 0
    if buf:
        chunks.append(
            ExtractedChunk(
                text=" ".join(buf).strip(),
                chunk_index=idx,
                start_time=buf_start,
                end_time=buf_end,
            )
        )
    return chunks


def detect_kind(filename: str, content_type: str | None = None) -> str:
    name = filename.lower()
    ext = Path(name).suffix.lstrip(".")
    if ext == "pdf":
        return "pdf"
    audio_ext = {"mp3", "wav", "m4a", "flac", "ogg", "aac", "oga", "webm"}
    video_ext = {"mp4", "mov", "mkv", "avi", "webm", "m4v"}
    if ext in audio_ext:
        return "audio"
    if ext in video_ext:
        return "video"
    if content_type:
        if content_type.startswith("audio/"):
            return "audio"
        if content_type.startswith("video/"):
            return "video"
        if content_type == "application/pdf":
            return "pdf"
    raise ValueError(f"Unsupported file type: {filename}")
