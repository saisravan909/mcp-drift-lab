# Failure Taxonomy for MCP and Agent Toolchains

Reliable agentic workflows require distinguishing between normal recoverable faults, silent data corruption, and runaway execution loops. `mcp-drift-lab` categorizes injected faults and resulting failure modes into four primary classes.

## 1. Schema Drift (`schema_drift`)

Schema drift occurs when an upstream MCP tool or backing API alters its response contract without prior consumer coordination.

- **Sub-types**:
  - `drop_field`: Removes an expected field (such as `status`) from the tool payload.
  - `rename_field`: Renames a key (such as `latency_ms` to `duration_ms`), causing naive consumers to miss telemetry or misinterpret values.
  - `wrong_type`: Coerces a field to an incompatible type (such as a string or null where an integer is expected).
- **Operational Impact**: Silent parsing errors, incorrect branching decisions, or unhandled runtime exceptions mid-workflow.
- **Mitigation (`schema_guard`)**: Normalizes recognized key aliases, attempts safe type coercion where unambiguous, and returns a structured fallback payload when required fields or types remain invalid.

## 2. Latency Spikes and Timeouts (`latency_spike`)

Latency degradation arises from downstream congestion, cold starts, or tail-latency jitter across multi-step tool chains.

- **Parameters**: Configurable `delay_ms`, deterministic `jitter_ms`, and optional `timeout_after_ms` thresholds.
- **Operational Impact**: Cascading step delays, budget exhaustion, and partial execution when downstream calls time out.
- **Mitigation (`loop_breaker` & Budgets)**: Enforces `max_elapsed_ms` and `max_tool_calls` limits so stalled workflows terminate cleanly rather than hanging indefinitely.

## 3. Transient Errors (`transient_error`)

Transient errors represent temporary availability or throttling failures (such as HTTP `429` or `503` equivalents) that may succeed on retry if bounded.

- **Parameters**: Configurable `fail_until_attempt`, `error_codes`, and `error_type`.
- **Operational Impact**: Unbounded retry storms, duplicate side effects when retries are not idempotent, or premature workflow failure when retries are omitted.
- **Mitigation (`loop_breaker` & `idempotency`)**: Caps per-tool retry counts (`max_retries_per_tool`) and tracks idempotency keys to prevent duplicate state changes.

## 4. Partial State Mutations (`partial_state`)

Partial state failures occur when a multi-step operation mutates workspace or external state in an earlier step and fails before completing subsequent dependent steps.

- **Parameters**: Configurable `fail_on_step`, `fail_after_mutations`, `error`, and `retryable`.
- **Operational Impact**: Split-brain or inconsistent system state (for example, a feature flag toggled without a corresponding incident record or with an aborted follow-up step).
- **Mitigation (`idempotency` Rollback & `no_uncompensated_mutations`)**: Records before/after state transitions during the run, performs reverse compensation on recorded mutations when a partial failure triggers, and flags any remaining uncompensated state in invariant checks.
