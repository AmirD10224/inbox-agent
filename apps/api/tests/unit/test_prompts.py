"""Unit tests for prompt loader + frontmatter parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from inbox_agent.agent.prompts import PromptLoader

if TYPE_CHECKING:
    from pathlib import Path


def test_loader_finds_classify_prompt() -> None:
    loader = PromptLoader()
    p = loader.load("classify")
    assert p.name == "classify"
    assert p.version == "1.0.0"
    assert p.model == "claude-sonnet-4-6"
    assert "support triage classifier" in p.system_template.lower()
    assert "{ticket}" in p.user_template


def test_loader_renders_user_template() -> None:
    loader = PromptLoader()
    p = loader.load("classify")
    _system, user = p.render(ticket="My invoice is wrong.")
    assert "My invoice is wrong." in user


def test_draft_prompt_has_faithfulness_rules() -> None:
    loader = PromptLoader()
    p = loader.load("draft")
    assert "faithfulness" in p.system_template.lower()


def test_escalate_prompt_lists_escalation_signals() -> None:
    loader = PromptLoader()
    p = loader.load("escalate")
    assert (
        "trust_safety" in p.system_template.lower() or "trust & safety" in p.system_template.lower()
    )


def test_unknown_prompt_raises() -> None:
    loader = PromptLoader()
    with pytest.raises(KeyError):
        loader.load("nonexistent")


def test_unknown_version_raises(tmp_path: Path) -> None:
    # Build a tiny dir with one prompt to exercise the version-miss path.
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "x.v1.0.0.md").write_text(
        "---\nname: x\nversion: 1.0.0\nmodel: claude-sonnet-4-6\n---\n\n"
        "# System\nhi\n\n# User\nhi {a}\n"
    )
    loader = PromptLoader(prompts_dir=d)
    with pytest.raises(FileNotFoundError):
        loader.load("x", version="9.9.9")


def test_load_caches(tmp_path: Path) -> None:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "x.v1.0.0.md").write_text(
        "---\nname: x\nversion: 1.0.0\nmodel: claude-sonnet-4-6\n---\n\n"
        "# System\nhi\n\n# User\nhi {a}\n"
    )
    loader = PromptLoader(prompts_dir=d)
    a = loader.load("x")
    b = loader.load("x")
    assert a is b


def test_missing_section_raises(tmp_path: Path) -> None:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "x.v1.0.0.md").write_text(
        "---\nname: x\nversion: 1.0.0\nmodel: claude-sonnet-4-6\n---\n\n# System\nhi\n"
    )
    loader = PromptLoader(prompts_dir=d)
    with pytest.raises(ValueError, match=r"System.*User"):
        loader.load("x")


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "x.v1.0.0.md").write_text("# System\nhi\n# User\nhi\n")
    loader = PromptLoader(prompts_dir=d)
    with pytest.raises(ValueError, match="frontmatter"):
        loader.load("x")
