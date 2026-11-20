# Contributing to `mcp-drift-lab`

Thanks for checking out `mcp-drift-lab`. Whether you are adding a reliability scenario, refining a guardrail, or reporting a bug in deterministic execution, small and focused contributions are very welcome.

## How This Project Is Structured

- `scenarios/*.yaml`: Declarative benchmark definitions specifying initial workspace state, expected tool sequences, fault profiles, and post-run invariants.
- `src/mcp_drift_lab/faults/`: Deterministic fault injectors (`schema_drift`, `latency_spike`, `transient_error`, `partial_state`).
- `src/mcp_drift_lab/guardrails/`: Runtime mitigations (`schema_guard`, `loop_breaker`, `idempotency`).
- `src/mcp_drift_lab/assertions/`: Post-run invariant checks (`invariants.py`).
- `src/mcp_drift_lab/runner.py`: Seeded `baseline` and `hardened` execution loop.
- `tests/`: Unit and end-to-end tests covering deterministic replay, trace serialization, and CLI execution.

## Adding a New Scenario

1. Create a new YAML file in `scenarios/` (for example, `scenarios/timeout_escalation.yaml`).
2. Define `scenario_id`, `title`, `description`, `goal_prompt`, `initial_state`, `allowed_tools`, `expected_sequence`, `invariants`, `fault_profile`, and `max_steps`.
3. Keep `initial_state` self-contained so `MockMCPWorkspace.reset()` can isolate every run cleanly.
4. Run `pytest -v` and `mcp-drift run --scenarios scenarios --modes baseline hardened --seeds 42 101` to verify deterministic behavior and inspect `summary.md`.

## Testing and Style Guidelines

- Target Python 3.11+ and keep public models and schemas typed with Pydantic v2.
- Ensure fault injectors and run logic remain deterministic for a given integer seed without relying on live network services.
- Keep documentation clear, factual, and free of emojis or promotional language.

## Submitting Changes

1. Branch from `main` and keep changes scoped to a single fault class, guardrail, scenario, or documentation improvement.
2. Confirm that unit and end-to-end tests pass in CI (`.github/workflows/eval-gate.yml`).
3. Open a pull request describing the failure mode addressed, how it was tested across seeds, and any behavioral trade-offs observed.
