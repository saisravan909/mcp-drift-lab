from __future__ import annotations

from typing import Any

from mcp_drift_lab.models import FaultConfig


def apply_partial_state_fault(
    fault: FaultConfig,
    step_index: int,
    mutation_index: int,
) -> dict[str, Any] | None:
    """Simulate a mid-workflow failure after prior state mutations have already occurred."""
    params = fault.parameters
    fail_on_step = params.get("fail_on_step")
    fail_after_mutations = int(params.get("fail_after_mutations", 1))
    error_message = str(params.get("error", "partial_state_write_failed"))

    step_matches = fail_on_step is not None and step_index == int(fail_on_step)
    mutations_exceeded = fail_on_step is None and mutation_index >= fail_after_mutations

    if not (step_matches or mutations_exceeded):
        return None

    return {
        "ok": False,
        "error": error_message,
        "partial_state": True,
        "step_index": step_index,
        "mutation_index": mutation_index,
        "retryable": bool(params.get("retryable", False)),
    }
