from mcp_drift_lab.guardrails import (
    IdempotencyGuard,
    LoopBreaker,
    validate_and_normalize_payload,
)


def test_schema_guard_normalizes_alias_and_triggers_fallback() -> None:
    aliased = validate_and_normalize_payload(
        {"ok": True, "status": "healthy", "duration_ms": "85"},
        required_fields=["ok", "status"],
        field_types={"latency_ms": "int"},
        aliases={"latency_ms": "duration_ms"},
    )
    assert aliased["valid"] is True
    assert aliased["payload"]["latency_ms"] == 85

    broken = validate_and_normalize_payload(
        {"ok": True},
        required_fields=["ok", "status"],
    )
    assert broken["valid"] is False
    assert broken["triggered"] is True


def test_loop_breaker_blocks_excess_duplicate_calls() -> None:
    breaker = LoopBreaker(max_tool_calls=10, max_duplicate_calls=2)
    args = {"service_name": "auth-service"}

    assert breaker.check_before_call("read_service_health", args)["allowed"] is True
    assert breaker.check_before_call("read_service_health", args)["allowed"] is True
    blocked = breaker.check_before_call("read_service_health", args)
    assert blocked["allowed"] is False
    assert blocked["reason"] == "duplicate_call_loop_detected"


def test_idempotency_guard_rolls_back_mutations() -> None:
    guard = IdempotencyGuard()
    state = {
        "feature_flags": {"circuit_breaker_v2": True},
        "incidents": [{"id": "INC-101", "title": "Test"}],
    }
    guard.record_mutation(
        0,
        action="update_config_flag",
        target="feature_flags.circuit_breaker_v2",
        before=False,
        after=True,
    )
    guard.record_mutation(
        1,
        action="create_incident_note",
        target="incidents[0]",
        before=None,
        after=state["incidents"][0],
    )

    rollback = guard.rollback_to_state(state)
    assert rollback["triggered"] is True
    assert state["feature_flags"]["circuit_breaker_v2"] is False
    assert state["incidents"] == []
    assert guard.has_uncompensated_mutations() is False
