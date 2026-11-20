from mcp_drift_lab.assertions.invariants import evaluate_invariants
from mcp_drift_lab.models import ExecutionMode, InvariantSpec, TraceEvent, TraceEventType


def _sample_trace(tool_name: str, step_index: int = 0) -> TraceEvent:
    return TraceEvent(
        timestamp_mono_ns=1_000_000 + step_index,
        run_id="run-test-01",
        scenario_id="scen-test-01",
        mode=ExecutionMode.HARDENED,
        step_index=step_index,
        event_type=TraceEventType.TOOL_REQUEST,
        tool_name=tool_name,
        payload_summary={},
        duration_ms=5.0,
    )


def test_invariants_pass_when_within_budgets_and_state_clean() -> None:
    specs = [
        InvariantSpec(name="max_retries_ok", rule_type="max_retries", parameters={"max_retries": 2}),
        InvariantSpec(name="max_calls_ok", rule_type="max_tool_calls", parameters={"max_calls": 5}),
        InvariantSpec(name="state_clean", rule_type="no_uncompensated_mutations", parameters={}),
        InvariantSpec(
            name="flag_enabled",
            rule_type="state_equals",
            parameters={"path": "feature_flags.circuit_breaker_v2", "expected": True},
        ),
    ]
    traces = [_sample_trace("read_service_health", 0), _sample_trace("update_config_flag", 1)]
    result = evaluate_invariants(
        specs,
        final_state={"feature_flags": {"circuit_breaker_v2": True}},
        traces=traces,
        tool_calls_count=2,
        retry_count=1,
        has_uncompensated_mutations=False,
        allowed_tools=["read_service_health", "update_config_flag"],
    )
    assert result["passed"] is True


def test_invariants_fail_on_uncompensated_mutation_and_disallowed_tool() -> None:
    specs = [
        InvariantSpec(name="state_clean", rule_type="no_uncompensated_mutations", parameters={}),
        InvariantSpec(name="allowed_only", rule_type="allowed_tools_only", parameters={}),
    ]
    traces = [_sample_trace("forbidden_shell_tool", 0)]
    result = evaluate_invariants(
        specs,
        final_state={},
        traces=traces,
        tool_calls_count=1,
        retry_count=0,
        has_uncompensated_mutations=True,
        allowed_tools=["read_service_health"],
    )
    assert result["passed"] is False
