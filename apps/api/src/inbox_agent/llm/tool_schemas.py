"""Forced-JSON via Anthropic tool-use.

Each agent stage defines a tool whose `input_schema` is the desired output
shape. By passing `tool_choice={"type": "tool", "name": ...}`, the model is
forced to emit a `tool_use` block whose `input` field already conforms to the
schema, no JSON parsing of free text required.

Schema repair: if the input fails Pydantic validation (rare but possible if
the model emits a stringified number), `repair_with_pydantic` retries once
with a tighter prompt. After two failures we surface the validation error.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AnthropicTool(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]


# ─── Classify ──────────────────────────────────────────────────────────────


class ClassifyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["billing", "technical", "account", "refund", "other"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=10, max_length=500)


CLASSIFY_TOOL: AnthropicTool = {
    "name": "record_classification",
    "description": (
        "Record the support ticket classification. Always call this exactly once with the "
        "best-fit category, calibrated confidence in [0, 1], and a one-sentence rationale."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["billing", "technical", "account", "refund", "other"],
                "description": "The single best-fit category. Use 'other' only when none apply.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Calibrated probability the category is correct. Use 0.95+ only "
                    "when extremely confident; 0.5-0.7 when ambiguous."
                ),
            },
            "rationale": {
                "type": "string",
                "minLength": 10,
                "maxLength": 500,
                "description": "One sentence explaining the decision.",
            },
        },
        "required": ["category", "confidence", "rationale"],
        "additionalProperties": False,
    },
}


# ─── Draft ─────────────────────────────────────────────────────────────────


class DraftCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    faq_id: str
    quote: str = Field(min_length=1, max_length=500)


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=20, max_length=2000)
    citations: list[DraftCitation] = Field(default_factory=list)
    tone: Literal["empathetic", "neutral", "apologetic", "informative"]


DRAFT_TOOL: AnthropicTool = {
    "name": "record_draft",
    "description": (
        "Record the customer-facing response. Cite FAQ chunks by id when used. "
        "If no FAQ context was provided, citations must be empty."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "response": {
                "type": "string",
                "minLength": 20,
                "maxLength": 2000,
                "description": "The full reply to the customer. Plain text, no markdown.",
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "faq_id": {"type": "string"},
                        "quote": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "required": ["faq_id", "quote"],
                    "additionalProperties": False,
                },
                "description": "Quoted text from FAQ chunks actually used. Empty if none.",
            },
            "tone": {
                "type": "string",
                "enum": ["empathetic", "neutral", "apologetic", "informative"],
            },
        },
        "required": ["response", "citations", "tone"],
        "additionalProperties": False,
    },
}


# ─── Escalate ──────────────────────────────────────────────────────────────


class EscalateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    escalate: bool
    reasoning: str = Field(min_length=10, max_length=500)
    suggested_team: Literal["billing", "engineering", "trust_safety", "general", "none"]


ESCALATE_TOOL: AnthropicTool = {
    "name": "record_escalation_decision",
    "description": (
        "Decide whether this ticket should go to a human. Escalate if confidence is low, "
        "the issue involves money/legal/safety, or the user is angry."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "escalate": {
                "type": "boolean",
                "description": "True iff a human should handle this ticket.",
            },
            "reasoning": {
                "type": "string",
                "minLength": 10,
                "maxLength": 500,
                "description": "Why escalate or not. Reference specific signals from the ticket.",
            },
            "suggested_team": {
                "type": "string",
                "enum": ["billing", "engineering", "trust_safety", "general", "none"],
                "description": "Which team. Use 'none' iff escalate is False.",
            },
        },
        "required": ["escalate", "reasoning", "suggested_team"],
        "additionalProperties": False,
    },
}


# ─── Judge (eval suite) ────────────────────────────────────────────────────


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    label: Literal["correct", "partially_correct", "incorrect"]
    reasoning: str = Field(min_length=5, max_length=400)


JUDGE_TOOL: AnthropicTool = {
    "name": "record_judgment",
    "description": (
        "Judge whether the agent's response is faithful to the FAQ context and "
        "addresses the user's ticket. Be strict, partial credit only when most of "
        "the answer is correct but key details are missing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "label": {
                "type": "string",
                "enum": ["correct", "partially_correct", "incorrect"],
            },
            "reasoning": {
                "type": "string",
                "minLength": 5,
                "maxLength": 400,
            },
        },
        "required": ["score", "label", "reasoning"],
        "additionalProperties": False,
    },
}


# ─── Repair helper ─────────────────────────────────────────────────────────


def repair_with_pydantic[T: BaseModel](model: type[T], data: dict[str, Any]) -> T:
    """Validate a tool-use payload via Pydantic. Re-raises with a clean error.

    The caller decides whether to retry the LLM call on `ValidationError`.
    """
    try:
        return model.model_validate(data)
    except ValidationError:
        raise
