from __future__ import annotations

import random
import time
from typing import Any

from mcp_drift_lab.models import FaultConfig


def compute_latency_delay_ms(fault: FaultConfig, seed: int, step_index: int) -> float:
    """Compute deterministic latency delay in milliseconds from FaultConfig parameters."""
    params = fault.parameters
    base_ms = float(params.get("delay_ms", 250.0))
    jitter_ms = float(params.get("jitter_ms", 0.0))
    timeout_after_ms = params.get("timeout_after_ms")

    rng = random.Random(f"{seed}:{step_index}:{fault.fault_type}")
    jitter = rng.uniform(0.0, jitter_ms) if jitter_ms > 0 else 0.0
    total_ms = max(0.0, base_ms + jitter)

    if timeout_after_ms is not None and total_ms > float(timeout_after_ms):
        return float(timeout_after_ms)
    return total_ms


def apply_latency_fault(
    fault: FaultConfig,
    seed: int,
    step_index: int,
    *,
    sleep: bool = False,
) -> dict[str, Any]:
    """Compute (and optionally sleep for) an injected latency spike or timeout."""
    params = fault.parameters
    delay_ms = compute_latency_delay_ms(fault, seed, step_index)
    timeout_after_ms = params.get("timeout_after_ms")
    timed_out = timeout_after_ms is not None and delay_ms >= float(timeout_after_ms)

    if sleep and delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    return {
        "injected_delay_ms": round(delay_ms, 3),
        "timed_out": timed_out,
        "simulated_sleep": sleep,
        "seed": seed,
        "step_index": step_index,
    }
