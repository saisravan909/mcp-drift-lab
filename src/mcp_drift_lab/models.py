from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionMode(StrEnum):
    BASELINE = "baseline"
    HARDENED = "hardened"


class FaultType(StrEnum):
    SCHEMA_DRIFT = "schema_drift"
    LATENCY_SPIKE = "latency_spike"
    TRANSIENT_ERROR = "transient_error"
    PARTIAL_STATE = "partial_state"


class TraceEventType(StrEnum):
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    FAULT_INJECTED = "fault_injected"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    STATE_MUTATION = "state_mutation"
    ERROR = "error"


class FaultConfig(BaseModel):
    fault_type: FaultType
    enabled: bool = True
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    trigger_on_tool: str | None = None
    trigger_on_step: int | None = Field(default=None, ge=0)
    seed: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class InvariantSpec(BaseModel):
    name: str
    rule_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    scenario_id: str
    title: str
    description: str
    goal_prompt: str
    initial_state: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    expected_sequence: list[str] = Field(default_factory=list)
    invariants: list[InvariantSpec] = Field(default_factory=list)
    fault_profile: list[FaultConfig] = Field(default_factory=list)
    max_steps: int = Field(default=12, ge=1)


class TraceEvent(BaseModel):
    timestamp_mono_ns: int
    run_id: str
    scenario_id: str
    mode: ExecutionMode
    step_index: int = Field(ge=0)
    event_type: TraceEventType
    tool_name: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(default=0.0, ge=0.0)


class RunResult(BaseModel):
    run_id: str
    scenario_id: str
    mode: ExecutionMode
    seed: int
    task_completed: bool
    invariants_passed: bool
    tool_calls_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    guardrail_interventions: int = Field(ge=0)
    total_latency_ms: float = Field(ge=0.0, ge=0.0)
    final_state_clean: bool
    failure_reason: str | None = None
    final_state: dict[str, Any] = Field(default_factory=dict)
    traces: list[TraceEvent] = Field(default_factory=list)
