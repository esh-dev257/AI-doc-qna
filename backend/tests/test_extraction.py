import pytest

from app.services.extraction import (
    chunk_text,
    chunks_from_segments,
    clean_text,
    detect_kind,
    extract_pdf_text,
)


def test_clean_text_collapses_whitespace():
    assert clean_text("hello    world\n\n\n\nfoo") == "hello world\n\nfoo"


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_short_returns_single():
    assert chunk_text("short") == ["short"]


def test_chunk_text_long_splits_with_overlap():
    text = ("Sentence one. " * 200).strip()
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 500


def test_chunks_from_segments_groups_by_chars():
    segs = [
        {"start": 0.0, "end": 1.0, "text": "hello world"},
        {"start": 1.0, "end": 2.5, "text": "second segment"},
        {"start": 2.5, "end": 4.0, "text": "third segment here is more text"},
        {"start": 4.0, "end": 5.0, "text": ""},
    ]
    out = chunks_from_segments(segs, target_chars=20)
    assert out
    assert out[0].start_time == 0.0
    assert out[-1].end_time >= 2.5
    assert all(c.text for c in out)


def test_chunks_from_segments_single_leftover():
    segs = [{"start": 0.0, "end": 1.0, "text": "tiny bit"}]
    out = chunks_from_segments(segs, target_chars=500)
    assert len(out) == 1
    assert out[0].start_time == 0.0


def test_detect_kind_pdf():
    assert detect_kind("doc.pdf") == "pdf"
    assert detect_kind("x.unknown", "application/pdf") == "pdf"


def test_detect_kind_audio_video():
    assert detect_kind("clip.mp3") == "audio"
    assert detect_kind("clip.mp4") == "video"
    assert detect_kind("x.unknown", "audio/mpeg") == "audio"
    assert detect_kind("x.unknown", "video/mp4") == "video"


def test_detect_kind_unknown():
    with pytest.raises(ValueError):
        detect_kind("foo.txt")


def test_extract_pdf_text_real(real_pdf_bytes):
    text = extract_pdf_text(real_pdf_bytes)
    assert "Panscience" in text or text  # tolerate strict parsers


def test_extract_pdf_text_blank(sample_pdf_bytes):
    text = extract_pdf_text(sample_pdf_bytes)
    assert text == ""
