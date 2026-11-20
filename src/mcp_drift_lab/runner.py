from __future__ import annotations

import time
from copy import deepcopy
from typing import Any
from uuid import uuid4

from fixtures.mock_mcp_servers.config_store import ConfigStoreMockServer
from fixtures.mock_mcp_servers.service_status import ServiceStatusMockServer
from fixtures.mock_mcp_servers.state_store import MockMCPWorkspace
from mcp_drift_lab.assertions.invariants import evaluate_invariants
from mcp_drift_lab.faults import dispatch_fault, should_trigger_fault
from mcp_drift_lab.guardrails import (
    IdempotencyGuard,
    LoopBreaker,
    validate_and_normalize_payload,
)
from mcp_drift_lab.models import (
    ExecutionMode,
    FaultConfig,
    FaultType,
    RunResult,
    Scenario,
    TraceEvent,
    TraceEventType,
)


def run_scenario(
    scenario: Scenario,
    *,
    mode: ExecutionMode = ExecutionMode.BASELINE,
    seed: int = 42,
    sleep_latency: bool = False,
) -> RunResult:
    """Execute a single deterministic run of a Scenario in baseline or hardened mode."""
    run_id = f"{scenario.scenario_id}-{mode.value}-s{seed}-{uuid4().hex[:8]}"
    workspace = MockMCPWorkspace(initial_state=scenario.initial_state)
    workspace.reset(scenario.initial_state)

    health_server = ServiceStatusMockServer(workspace)
    config_server = ConfigStoreMockServer(workspace)

    traces: list[TraceEvent] = []
    tool_calls_count = 0
    retry_count = 0
    guardrail_interventions = 0
    mutation_count = 0
    task_completed = False
    failure_reason: str | None = None

    loop_breaker = LoopBreaker(
        max_tool_calls=scenario.max_steps,
        max_retries_per_tool=2 if mode == ExecutionMode.HARDENED else 5,
        max_duplicate_calls=2 if mode == ExecutionMode.HARDENED else 6,
        max_elapsed_ms=10_000.0,
    )
    idempotency = IdempotencyGuard()

    run_start_ns = time.monotonic_ns()

    def emit(
        step_idx: int,
        event_type: TraceEventType,
        *,
        tool_name: str | None = None,
        payload_summary: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        traces.append(
            TraceEvent(
                timestamp_mono_ns=time.monotonic_ns(),
                run_id=run_id,
                scenario_id=scenario.scenario_id,
                mode=mode,
                step_index=step_idx,
                event_type=event_type,
                tool_name=tool_name,
                payload_summary=payload_summary or {},
                duration_ms=max(0.0, duration_ms),
            )
        )

    plan = _build_plan(scenario)

    for step_idx, action in enumerate(plan):
        tool_name = action["tool"]
        args = action["args"]
        is_retry = bool(action.get("is_retry", False))
        attempt = int(action.get("attempt", 1))
        idem_key = action.get("idempotency_key")

        if is_retry:
            retry_count += 1

        step_start_ns = time.monotonic_ns()

        # Check allowed tools if specified
        if scenario.allowed_tools and tool_name not in scenario.allowed_tools:
            failure_reason = f"disallowed_tool:{tool_name}"
            emit(
                step_idx,
                TraceEventType.ERROR,
                tool_name=tool_name,
                payload_summary={"error": failure_reason},
                duration_ms=(time.monotonic_ns() - step_start_ns) / 1_000_000.0,
            )
            break

        # In hardened mode, enforce loop breaker and duplicate idempotency key checks
        if mode == ExecutionMode.HARDENED:
            lb_decision = loop_breaker.check_before_call(
                tool_name,
                args,
                is_retry=is_retry,
                step_elapsed_ms=(time.monotonic_ns() - run_start_ns) / 1_000_000.0,
            )
            if not lb_decision["allowed"]:
                guardrail_interventions += 1
                failure_reason = str(lb_decision["reason"])
                emit(
                    step_idx,
                    TraceEventType.GUARDRAIL_TRIGGERED,
                    tool_name=tool_name,
                    payload_summary={"guardrail": "loop_breaker", **lb_decision},
                    duration_ms=(time.monotonic_ns() - step_start_ns) / 1_000_000.0,
                )
                break

            if idempotency.is_duplicate_mutation(idem_key):
                guardrail_interventions += 1
                emit(
                    step_idx,
                    TraceEventType.GUARDRAIL_TRIGGERED,
                    tool_name=tool_name,
                    payload_summary={
                        "guardrail": "idempotency_dedup",
                        "idempotency_key": idem_key,
                    },
                    duration_ms=(time.monotonic_ns() - step_start_ns) / 1_000_000.0,
                )
                continue

        tool_calls_count += 1
        emit(
            step_idx,
            TraceEventType.TOOL_REQUEST,
            tool_name=tool_name,
            payload_summary={"args": args, "attempt": attempt},
        )

        # Evaluate matching faults for this step and tool
        injected_latency_ms = 0.0
        error_payload: dict[str, Any] | None = None
        schema_faults: list[FaultConfig] = []

        for fault in scenario.fault_profile:
            if not should_trigger_fault(fault, seed, step_idx, tool_name):
                continue

            fault_res = dispatch_fault(
                fault,
                seed,
                step_idx,
                attempt=attempt,
                mutation_index=mutation_count,
                sleep_latency=sleep_latency,
            )
            emit(
                step_idx,
                TraceEventType.FAULT_INJECTED,
                tool_name=tool_name,
                payload_summary={
                    "fault_type": fault.fault_type.value,
                    "details": fault_res.get("details", {}),
                },
            )

            if fault.fault_type == FaultType.LATENCY_SPIKE:
                injected_latency_ms += float(fault_res["details"].get("injected_delay_ms", 0.0))
                if fault_res["details"].get("timed_out"):
                    error_payload = {
                        "ok": False,
                        "error": "tool_timeout",
                        "delay_ms": injected_latency_ms,
                    }
            elif fault.fault_type in (FaultType.TRANSIENT_ERROR, FaultType.PARTIAL_STATE):
                if fault_res.get("error_response") is not None:
                    error_payload = fault_res["error_response"]
            elif fault.fault_type == FaultType.SCHEMA_DRIFT:
                schema_faults.append(fault)

        # If a fault produced an error, handle recovery or fail
        if error_payload is not None:
            emit(
                step_idx,
                TraceEventType.ERROR,
                tool_name=tool_name,
                payload_summary=error_payload,
                duration_ms=((time.monotonic_ns() - step_start_ns) / 1_000_000.0)
                + injected_latency_ms,
            )

            if mode == ExecutionMode.HARDENED and error_payload.get("partial_state"):
                rb = idempotency.rollback_to_state(workspace.state)
                if rb["triggered"]:
                    guardrail_interventions += 1
                    emit(
                        step_idx,
                        TraceEventType.GUARDRAIL_TRIGGERED,
                        tool_name=tool_name,
                        payload_summary={"guardrail": "idempotency_rollback", **rb},
                    )
                failure_reason = str(error_payload.get("error", "partial_state_failure"))
                break

            if mode == ExecutionMode.HARDENED and error_payload.get("retryable"):
                guardrail_interventions += 1
                # Inject a single bounded recovery retry if available in scenario
                failure_reason = str(error_payload.get("error", "transient_error"))
                break

            failure_reason = str(error_payload.get("error", "tool_error"))
            break

        # Invoke underlying mock MCP tool
        response = _invoke_mock_tool(health_server, config_server, tool_name, args)

        # Track state mutations if tool modified workspace
        if response.get("ok") and tool_name in ("update_config_flag", "create_incident_note"):
            mutation_count += 1
            if tool_name == "update_config_flag":
                idempotency.record_mutation(
                    step_idx,
                    action="update_config_flag",
                    target=f"feature_flags.{args.get('flag_name')}",
                    before=response.get("previous_value"),
                    after=response.get("enabled"),
                    idempotency_key=idem_key,
                )
            elif tool_name == "create_incident_note":
                inc = response.get("incident", {})
                idempotency.record_mutation(
                    step_idx,
                    action="create_incident_note",
                    target=f"incidents[{len(workspace.state.get('incidents', [])) - 1}]",
                    before=None,
                    after=inc,
                    idempotency_key=idem_key,
                )
            emit(
                step_idx,
                TraceEventType.STATE_MUTATION,
                tool_name=tool_name,
                payload_summary={
                    "mutation_index": mutation_count,
                    "target": tool_name,
                },
            )

        # Apply schema drift faults to response payload
        for sf in schema_faults:
            drifted = dispatch_fault(sf, seed, step_idx, payload=response)
            response = drifted["mutated_payload"]

        # In hardened mode, validate and normalize response payload
        if mode == ExecutionMode.HARDENED:
            guard_res = validate_and_normalize_payload(
                response,
                required_fields=["ok"] if "ok" in response else [],
                field_types={"latency_ms": "int"},
                aliases={"latency_ms": "duration_ms"},
            )
            if guard_res["triggered"]:
                guardrail_interventions += 1
                response = guard_res["payload"]
                emit(
                    step_idx,
                    TraceEventType.GUARDRAIL_TRIGGERED,
                    tool_name=tool_name,
                    payload_summary={"guardrail": "schema_guard", **guard_res},
                )

        step_duration_ms = ((time.monotonic_ns() - step_start_ns) / 1_000_000.0) + injected_latency_ms
        emit(
            step_idx,
            TraceEventType.TOOL_RESPONSE,
            tool_name=tool_name,
            payload_summary={"ok": response.get("ok", True), "keys": sorted(response.keys())},
            duration_ms=step_duration_ms,
        )

    total_latency_ms = max(
        0.0,
        ((time.monotonic_ns() - run_start_ns) / 1_000_000.0)
        + sum(
            float(ev.payload_summary.get("details", {}).get("injected_delay_ms", 0.0))
            for ev in traces
            if ev.event_type == TraceEventType.FAULT_INJECTED
        ),
    )

    uncompensated = idempotency.has_uncompensated_mutations()
    inv_eval = evaluate_invariants(
        scenario.invariants,
        final_state=workspace.state,
        traces=traces,
        tool_calls_count=tool_calls_count,
        retry_count=retry_count,
        has_uncompensated_mutations=uncompensated,
        allowed_tools=scenario.allowed_tools,
    )

    if failure_reason is None and len(plan) > 0:
        task_completed = True

    return RunResult(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        mode=mode,
        seed=seed,
        task_completed=task_completed,
        invariants_passed=bool(inv_eval["passed"]),
        tool_calls_count=tool_calls_count,
        retry_count=retry_count,
        guardrail_interventions=guardrail_interventions,
        total_latency_ms=round(total_latency_ms, 3),
        final_state_clean=not uncompensated,
        failure_reason=failure_reason,
        final_state=deepcopy(workspace.state),
        traces=traces,
    )


def _build_plan(scenario: Scenario) -> list[dict[str, Any]]:
    """Derive a deterministic step sequence from scenario.expected_sequence or defaults."""
    if scenario.expected_sequence:
        steps: list[dict[str, Any]] = []
        for idx, tool_name in enumerate(scenario.expected_sequence):
            if tool_name == "read_service_health":
                args = {"service_name": "auth-service"}
            elif tool_name == "update_config_flag":
                args = {"flag_name": "circuit_breaker_v2", "enabled": True}
            elif tool_name == "create_incident_note":
                args = {
                    "title": f"Automated check for {scenario.scenario_id}",
                    "severity": "medium",
                    "summary": "Recorded during scenario execution.",
                }
            else:
                args = {}
            steps.append(
                {
                    "tool": tool_name,
                    "args": args,
                    "is_retry": False,
                    "attempt": 1,
                    "idempotency_key": f"{scenario.scenario_id}:step-{idx}:{tool_name}",
                }
            )
        return steps

    return [
        {
            "tool": "read_service_health",
            "args": {"service_name": "auth-service"},
            "is_retry": False,
            "attempt": 1,
            "idempotency_key": f"{scenario.scenario_id}:0:read_service_health",
        },
        {
            "tool": "update_config_flag",
            "args": {"flag_name": "circuit_breaker_v2", "enabled": True},
            "is_retry": False,
            "attempt": 1,
            "idempotency_key": f"{scenario.scenario_id}:1:update_config_flag",
        },
    ]


def _invoke_mock_tool(
    health_server: ServiceStatusMockServer,
    config_server: ConfigStoreMockServer,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "read_service_health":
        return health_server.read_service_health(
            service_name=str(args.get("service_name", "auth-service"))
        )
    if tool_name == "update_config_flag":
        return config_server.update_config_flag(
            flag_name=str(args.get("flag_name", "circuit_breaker_v2")),
            enabled=bool(args.get("enabled", True)),
        )
    if tool_name == "create_incident_note":
        return config_server.create_incident_note(
            title=str(args.get("title", "Incident")),
            severity=str(args.get("severity", "medium")),
            summary=str(args.get("summary", "")),
        )
    return {"ok": False, "error": f"unknown_tool:{tool_name}"}
