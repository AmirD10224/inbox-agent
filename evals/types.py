"""Eval types: golden item, run record, scorecard."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ExpectedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    escalate: bool
    suggested_team: Literal["billing", "engineering", "trust_safety", "general", "none"]


class GoldenItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    ticket: str
    expected_class: Literal["billing", "technical", "account", "refund", "other"]
    expected_action: ExpectedAction
    expected_answer_contains: list[str] = []


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    ticket: str
    expected_class: str
    actual_class: str
    expected_escalate: bool
    actual_escalate: bool
    expected_team: str
    actual_team: str
    confidence: float
    drafted_response: str
    judge_score: float
    judge_label: Literal["correct", "partially_correct", "incorrect"]
    judge_reasoning: str
    cost_usd: float
    latency_ms: int


class Scorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    classification_accuracy: float
    escalation_accuracy: float
    team_accuracy: float
    judge_mean_score: float
    hallucination_rate: float  # judge_label == "incorrect"
    p50_latency_ms: int
    p95_latency_ms: int
    avg_cost_usd: float
    total_cost_usd: float
    per_class_accuracy: dict[str, float]
    failures: list[str]  # ids where judge marked incorrect or class wrong
    git_sha: str | None = None
    timestamp: str
