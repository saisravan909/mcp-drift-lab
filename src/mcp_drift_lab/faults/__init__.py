from __future__ import annotations

import random
from typing import Any

from mcp_drift_lab.models import FaultConfig, FaultType

from .latency import apply_latency_fault
from .partial_state import apply_partial_state_fault
from .schema_drift import apply_schema_drift
from .transient_errors import apply_transient_error


def should_trigger_fault(
    fault: FaultConfig,
    seed: int,
    step_index: int,
    tool_name: str | None = None,
) -> bool:
    """Determine deterministically whether a FaultConfig fires for this call."""
    if not fault.enabled:
        return False
    if fault.trigger_on_tool is not None and tool_name != fault.trigger_on_tool:
        return False
    if fault.trigger_on_step is not None and step_index != fault.trigger_on_step:
        return False

    effective_seed = fault.seed if fault.seed is not None else seed
    rng = random.Random(f"{effective_seed}:{step_index}:{tool_name}:{fault.fault_type}")
    return rng.random() <= fault.probability


def dispatch_fault(
    fault: FaultConfig,
    seed: int,
    step_index: int,
    *,
    payload: dict[str, Any] | None = None,
    attempt: int = 1,
    mutation_index: int = 0,
    sleep_latency: bool = False,
) -> dict[str, Any]:
    """Execute a specific fault injector and return structured fault metadata (and payload if drifted)."""
    effective_seed = fault.seed if fault.seed is not None else seed

    if fault.fault_type == FaultType.SCHEMA_DRIFT:
        drifted_payload, details = apply_schema_drift(payload or {}, fault, effective_seed)
        return {
            "fault_type": fault.fault_type,
            "triggered": True,
            "mutated_payload": drifted_payload,
            "details": details,
        }

    if fault.fault_type == FaultType.LATENCY_SPIKE:
        details = apply_latency_fault(fault, effective_seed, step_index, sleep=sleep_latency)
        return {
            "fault_type": fault.fault_type,
            "triggered": True,
            "details": details,
        }

    if fault.fault_type == FaultType.TRANSIENT_ERROR:
        err = apply_transient_error(fault, effective_seed, step_index, attempt=attempt)
        return {
            "fault_type": fault.fault_type,
            "triggered": err is not None,
            "error_response": err,
            "details": err or {"triggered": False, "attempt": attempt},
        }

    if fault.fault_type == FaultType.PARTIAL_STATE:
        err = apply_partial_state_fault(fault, step_index, mutation_index)
        return {
            "fault_type": fault.fault_type,
            "triggered": err is not None,
            "error_response": err,
            "details": err or {"triggered": False, "mutation_index": mutation_index},
        }

    raise ValueError(f"Unsupported fault type: {fault.fault_type}")


__all__ = [
    "apply_latency_fault",
    "apply_partial_state_fault",
    "apply_schema_drift",
    "apply_transient_error",
    "dispatch_fault",
    "should_trigger_fault",
]
