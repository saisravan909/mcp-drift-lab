from __future__ import annotations

import random
from typing import Any

from mcp_drift_lab.models import FaultConfig


def apply_transient_error(
    fault: FaultConfig,
    seed: int,
    step_index: int,
    attempt: int = 1,
) -> dict[str, Any] | None:
    """Return a simulated transient error payload if triggered, or None if healthy."""
    params = fault.parameters
    fail_until_attempt = int(params.get("fail_until_attempt", 1))
    error_codes: list[int] = list(params.get("error_codes", [429, 503]))
    error_type = str(params.get("error_type", "transient_http"))

    if attempt > fail_until_attempt:
        return None

    rng = random.Random(f"{seed}:{step_index}:{attempt}:{fault.fault_type}")
    code = rng.choice(error_codes) if error_codes else 503

    return {
        "ok": False,
        "error": f"transient_error:{code}",
        "error_type": error_type,
        "status_code": code,
        "retryable": True,
        "attempt": attempt,
        "fail_until_attempt": fail_until_attempt,
    }
