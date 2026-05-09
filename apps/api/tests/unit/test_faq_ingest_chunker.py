"""Unit tests for the FAQ chunker (pure function, no I/O)."""

from __future__ import annotations

from inbox_agent.faq.ingest import _chunk


def test_chunk_short_text_single_chunk() -> None:
    text = "Q: How do I reset my password?\n\nA: Go to Settings > Security > Reset Password."
    chunks = _chunk(text, target_tokens=400, overlap_tokens=50)
    assert len(chunks) == 1
    assert "reset" in chunks[0].lower()


def test_chunk_long_text_splits() -> None:
    paragraphs = [f"Paragraph {i}: " + "lorem ipsum " * 80 for i in range(8)]
    text = "\n\n".join(paragraphs)
    chunks = _chunk(text, target_tokens=400, overlap_tokens=50)
    assert len(chunks) >= 2
    for c in chunks:
        # Soft check: chunks shouldn't grossly exceed target * chars_per_token * 1.5.
        assert len(c) < 400 * 4 * 1.5 + 200


def test_chunk_overlap_preserves_context() -> None:
    paragraphs = [f"Section {i}: " + "alpha beta gamma delta epsilon. " * 50 for i in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = _chunk(text, target_tokens=300, overlap_tokens=80)
    if len(chunks) >= 2:
        # Some characters from chunk i should appear at the start of chunk i+1.
        tail_of_first = chunks[0][-100:]
        assert any(piece in chunks[1][:300] for piece in tail_of_first.split() if len(piece) > 4)


def test_chunk_keeps_single_short_doc() -> None:
    """Tiny single-chunk docs (e.g, a 30-char Q/A page) must still ingest."""
    text = "Hello world! Welcome to support."
    chunks = _chunk(text, target_tokens=400, overlap_tokens=50)
    assert chunks == [text]


def test_chunk_drops_scraps_only_when_more_than_one_chunk() -> None:
    """When the chunker produces 2+ chunks, sub-50-char scraps are filtered."""
    long_para = "alpha beta gamma delta epsilon. " * 60  # ~1800 chars
    short_scrap = "tiny"
    text = f"{long_para}\n\n{short_scrap}"
    chunks = _chunk(text, target_tokens=400, overlap_tokens=50)
    assert all(len(c) >= 50 for c in chunks)
    assert len(chunks) >= 2


def test_chunk_oversize_paragraph_hard_splits() -> None:
    """A single paragraph > target_chars must be split, not produce one mega-chunk."""
    huge_para = "lorem ipsum " * 1000  # ~12_000 chars
    target_tokens = 400
    overlap_tokens = 50
    chunks = _chunk(huge_para, target_tokens=target_tokens, overlap_tokens=overlap_tokens)
    target_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4
    # Each chunk is at most target_chars + overlap_chars (overlap is by design)
    # plus a small slop for the "\n\n" join separator.
    upper = target_chars + overlap_chars + 50
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= upper, f"chunk too large: {len(c)} > {upper}"


def test_chunk_empty_returns_empty() -> None:
    assert _chunk("", target_tokens=400, overlap_tokens=50) == []
    assert _chunk("   \n\n   \n", target_tokens=400, overlap_tokens=50) == []
