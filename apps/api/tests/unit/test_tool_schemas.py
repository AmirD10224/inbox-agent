"""Unit tests for tool schemas + Pydantic repair."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from inbox_agent.llm.tool_schemas import (
    CLASSIFY_TOOL,
    DRAFT_TOOL,
    ESCALATE_TOOL,
    JUDGE_TOOL,
    ClassifyOutput,
    DraftOutput,
    EscalateOutput,
    JudgeOutput,
    repair_with_pydantic,
)


def test_classify_tool_schema_required_fields() -> None:
    schema = CLASSIFY_TOOL["input_schema"]
    assert set(schema["required"]) == {"category", "confidence", "rationale"}
    assert schema["additionalProperties"] is False
    assert "billing" in schema["properties"]["category"]["enum"]


def test_classify_output_validates_enum() -> None:
    valid = ClassifyOutput(
        category="billing", confidence=0.9, rationale="clear billing wording in ticket"
    )
    assert valid.category == "billing"

    with pytest.raises(ValidationError):
        ClassifyOutput.model_validate(
            {"category": "weather", "confidence": 0.9, "rationale": "x" * 30}
        )


def test_classify_output_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ClassifyOutput.model_validate(
            {"category": "billing", "confidence": 1.5, "rationale": "x" * 30}
        )
    with pytest.raises(ValidationError):
        ClassifyOutput.model_validate(
            {"category": "billing", "confidence": -0.1, "rationale": "x" * 30}
        )


def test_draft_output_citations_optional() -> None:
    out = DraftOutput.model_validate(
        {"response": "Thanks for reaching out, happy to help.", "citations": [], "tone": "neutral"}
    )
    assert out.citations == []


def test_draft_tool_no_extra_fields_allowed() -> None:
    schema = DRAFT_TOOL["input_schema"]
    assert schema["additionalProperties"] is False


def test_escalate_team_enum() -> None:
    valid = EscalateOutput(
        escalate=True, reasoning="legal threat from user", suggested_team="trust_safety"
    )
    assert valid.suggested_team == "trust_safety"

    with pytest.raises(ValidationError):
        EscalateOutput.model_validate(
            {"escalate": True, "reasoning": "x" * 30, "suggested_team": "marketing"}
        )


def test_escalate_tool_schema_team_enum_matches_pydantic() -> None:
    schema_enum = set(ESCALATE_TOOL["input_schema"]["properties"]["suggested_team"]["enum"])
    expected = {"billing", "engineering", "trust_safety", "general", "none"}
    assert schema_enum == expected


def test_judge_tool_schema_includes_score_and_label() -> None:
    schema = JUDGE_TOOL["input_schema"]
    assert "score" in schema["properties"]
    assert "label" in schema["properties"]


def test_judge_output_label_enum() -> None:
    out = JudgeOutput.model_validate(
        {"score": 0.5, "label": "partially_correct", "reasoning": "missing detail"}
    )
    assert out.label == "partially_correct"


def test_repair_returns_validated_model() -> None:
    out = repair_with_pydantic(
        ClassifyOutput,
        {"category": "billing", "confidence": 0.8, "rationale": "x" * 30},
    )
    assert isinstance(out, ClassifyOutput)
    assert out.confidence == 0.8


def test_repair_raises_on_invalid_payload() -> None:
    with pytest.raises(ValidationError):
        repair_with_pydantic(
            ClassifyOutput,
            {"category": "billing", "confidence": 99, "rationale": "x" * 30},
        )
