from __future__ import annotations

from copy import deepcopy
from typing import Any

from mcp_drift_lab.models import FaultConfig


def apply_schema_drift(
    payload: dict[str, Any],
    fault: FaultConfig,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mutate a tool payload to simulate schema drift (dropped field, renamed key, or wrong type)."""
    mutated = deepcopy(payload)
    params = fault.parameters
    mode = str(params.get("drift_mode", "drop_field"))
    details: dict[str, Any] = {"drift_mode": mode, "seed": seed}

    if mode == "drop_field":
        field = str(params.get("field", "status"))
        existed = field in mutated
        mutated.pop(field, None)
        details.update({"field": field, "existed": existed})

    elif mode == "rename_field":
        old_key = str(params.get("old_key", "latency_ms"))
        new_key = str(params.get("new_key", "duration_ms"))
        existed = old_key in mutated
        if existed:
            mutated[new_key] = mutated.pop(old_key)
        details.update({"old_key": old_key, "new_key": new_key, "existed": existed})

    elif mode == "wrong_type":
        field = str(params.get("field", "latency_ms"))
        target_type = str(params.get("target_type", "string"))
        previous_value = mutated.get(field)
        if field in mutated:
            if target_type == "string":
                mutated[field] = str(previous_value)
            elif target_type == "int":
                try:
                    mutated[field] = int(previous_value)
                except (ValueError, TypeError):
                    mutated[field] = -1
            elif target_type == "bool":
                mutated[field] = bool(previous_value)
            else:
                mutated[field] = None
        details.update(
            {
                "field": field,
                "target_type": target_type,
                "previous_value": previous_value,
                "new_value": mutated.get(field),
            }
        )

    else:
        details["warning"] = f"unknown_drift_mode:{mode}"

    return mutated, details
