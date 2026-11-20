from __future__ import annotations

from typing import Any

from mcp_drift_lab.models import InvariantSpec, TraceEvent, TraceEventType


def evaluate_invariants(
    invariants: list[InvariantSpec],
    *,
    final_state: dict[str, Any],
    traces: list[TraceEvent],
    tool_calls_count: int,
    retry_count: int,
    has_uncompensated_mutations: bool,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate all scenario invariants and return overall pass/fail plus per-rule details."""
    results: list[dict[str, Any]] = []
    all_passed = True

    called_tools = [
        ev.tool_name
        for ev in traces
        if ev.event_type == TraceEventType.TOOL_REQUEST and ev.tool_name is not None
    ]

    for spec in invariants:
        rule = spec.rule_type
        params = spec.parameters
        passed = True
        detail: dict[str, Any] = {"name": spec.name, "rule_type": rule}

        if rule == "max_retries":
            max_allowed = int(params.get("max_retries", 2))
            passed = retry_count <= max_allowed
            detail.update({"retry_count": retry_count, "max_retries": max_allowed})

        elif rule == "max_tool_calls":
            max_calls = int(params.get("max_calls", 12))
            passed = tool_calls_count <= max_calls
            detail.update({"tool_calls_count": tool_calls_count, "max_calls": max_calls})

        elif rule == "no_uncompensated_mutations":
            passed = not has_uncompensated_mutations
            detail.update({"has_uncompensated_mutations": has_uncompensated_mutations})

        elif rule == "allowed_tools_only":
            permitted = set(allowed_tools if allowed_tools is not None else params.get("tools", []))
            disallowed = [t for t in called_tools if t not in permitted]
            passed = len(disallowed) == 0
            detail.update({"disallowed_tools": disallowed})

        elif rule == "required_tools_called":
            required = list(params.get("tools", []))
            missing = [t for t in required if t not in called_tools]
            passed = len(missing) == 0
            detail.update({"missing_tools": missing, "called_tools": called_tools})

        elif rule == "state_equals":
            path = str(params.get("path", ""))
            expected = params.get("expected")
            actual, found = _resolve_path(final_state, path)
            passed = found and actual == expected
            detail.update({"path": path, "expected": expected, "actual": actual, "found": found})

        else:
            passed = False
            detail["error"] = f"unknown_invariant_rule:{rule}"

        detail["passed"] = passed
        results.append(detail)
        if not passed:
            all_passed = False

    return {
        "passed": all_passed,
        "checks": results,
    }


def _resolve_path(data: dict[str, Any], dotted_path: str) -> tuple[Any, bool]:
    """Resolve a dotted key path like 'feature_flags.strict_rate_limit' inside nested dicts."""
    if not dotted_path:
        return None, False
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True
