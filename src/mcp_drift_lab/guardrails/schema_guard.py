from __future__ import annotations

from copy import deepcopy
from typing import Any


def validate_and_normalize_payload(
    payload: dict[str, Any],
    required_fields: list[str] | None = None,
    field_types: dict[str, str] | None = None,
    aliases: dict[str, str] | None = None,
    fallback_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate payload schema, normalize known key aliases, or produce a safe fallback."""
    normalized = deepcopy(payload)
    req_fields = required_fields or []
    expected_types = field_types or {}
    alias_map = aliases or {}
    violations: list[str] = []
    repairs: list[str] = []

    # Normalize renamed keys if target key is missing and alias is present
    for canonical_key, drifted_key in alias_map.items():
        if canonical_key not in normalized and drifted_key in normalized:
            normalized[canonical_key] = normalized.pop(drifted_key)
            repairs.append(f"aliased:{drifted_key}->{canonical_key}")

    # Check required fields
    for field in req_fields:
        if field not in normalized or normalized[field] is None:
            violations.append(f"missing_field:{field}")

    # Check and attempt safe type coercion for expected fields
    for field, exp_type in expected_types.items():
        if field not in normalized:
            continue
        val = normalized[field]
        if exp_type == "int":
            if isinstance(val, bool) or not isinstance(val, int):
                try:
                    coerced = int(val)
                    normalized[field] = coerced
                    repairs.append(f"coerced_int:{field}")
                except (ValueError, TypeError):
                    violations.append(f"invalid_type:{field}:expected_int")
        elif exp_type == "float":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                try:
                    coerced_f = float(val)
                    normalized[field] = coerced_f
                    repairs.append(f"coerced_float:{field}")
                except (ValueError, TypeError):
                    violations.append(f"invalid_type:{field}:expected_float")
        elif exp_type == "str":
            if not isinstance(val, str):
                violations.append(f"invalid_type:{field}:expected_str")
        elif exp_type == "bool":
            if not isinstance(val, bool):
                violations.append(f"invalid_type:{field}:expected_bool")

    if violations:
        safe_payload = deepcopy(fallback_payload) if fallback_payload is not None else {
            "ok": False,
            "degraded": True,
            "status": "unknown",
            "reason": "schema_guard_fallback",
        }
        return {
            "valid": False,
            "triggered": True,
            "violations": violations,
            "repairs": repairs,
            "payload": safe_payload,
        }

    return {
        "valid": True,
        "triggered": len(repairs) > 0,
        "violations": [],
        "repairs": repairs,
        "payload": normalized,
    }
