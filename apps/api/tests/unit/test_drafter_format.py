"""Unit tests for the drafter's FAQ context formatter."""

from __future__ import annotations

from inbox_agent.agent.drafter import format_faq_context
from inbox_agent.faq.retrieve import FAQContextItem


def test_format_no_items_emits_explicit_no_context() -> None:
    rendered = format_faq_context([])
    assert "No FAQ context" in rendered
    assert "human" in rendered  # ensures the model is told to defer.


def test_format_with_items_includes_ids_and_scores() -> None:
    items = [
        FAQContextItem(chunk_id="abc-1", text="Refunds within 30 days.", score=0.91),
        FAQContextItem(
            chunk_id="abc-2", text="Refunds processed in 5-7 business days.", score=0.83
        ),
    ]
    rendered = format_faq_context(items)
    assert "abc-1" in rendered
    assert "abc-2" in rendered
    assert "0.91" in rendered
    assert "Refunds within 30 days." in rendered


def test_format_score_formatting() -> None:
    items = [FAQContextItem(chunk_id="x", text="t", score=0.5)]
    rendered = format_faq_context(items)
    assert "0.50" in rendered
