# MCP Drift Lab Architecture

## Overview

`mcp-drift-lab` is a deterministic fault-injection and reliability evaluation harness for Model Context Protocol (MCP) servers and agent toolchains. It provides controlled, reproducible execution across `baseline` (unmitigated) and `hardened` (guardrail-enforced) modes so engineering teams and researchers can measure how tool drift, latency spikes, transient errors, and partial state mutations affect end-to-end execution integrity.

## Design Principles

- **Determinism Over Ad-Hoc Replay**: Every run is parameterized by an explicit integer seed and deterministic mock workspace state, enabling repeatable regression comparisons across commits and model/toolchain updates.
- **Separation of Goal Completion and System Invariants**: An agent or workflow may appear to complete a prompt while violating safety, retry, tool-scope, or state-consistency invariants. Both dimensions are evaluated independently.
- **Vendor-Neutral Harness**: Core contracts (`Scenario`, `FaultConfig`, `TraceEvent`, `RunResult`) are modeled with Pydantic v2 so scenarios can be authored declaratively in YAML or JSON and executed in CI without external network dependencies.
- **Auditable Telemetry**: Every step emits structured `TraceEvent` records with monotonic timestamps, supporting JSONL trace serialization and aggregate JSON/Markdown reporting.

## Component Layout

| Layer | Package / Path | Responsibility |
| --- | --- | --- |
| Domain Models | `src/mcp_drift_lab/models.py` | Strongly typed schemas for scenarios, faults, traces, and run outcomes. |
| Mock MCP Fixtures | `fixtures/mock_mcp_servers/` | Stateful workspace (`MockMCPWorkspace`) with explicit `reset()` isolation and mock service/config tools. |
| Fault Injectors | `src/mcp_drift_lab/faults/` | Deterministic injectors for schema drift, latency spikes, transient errors, and partial state failures. |
| Guardrails | `src/mcp_drift_lab/guardrails/` | Runtime protections including schema normalization/fallback, loop breaking, and idempotency rollback. |
| Invariant Engine | `src/mcp_drift_lab/assertions/` | Post-run evaluation of retry caps, call budgets, tool boundaries, state values, and compensation status. |
| Execution Runner | `src/mcp_drift_lab/runner.py` | Orchestrates scenario runs across `baseline` and `hardened` modes with workspace isolation and trace capture. |
| Reporting & CLI | `src/mcp_drift_lab/reporting/`, `src/mcp_drift_lab/cli.py` | Writes JSONL traces and summary reports (`summary.json`, `summary.md`) and enforces CI pass-rate gates. |
| Scenario Definitions | `scenarios/*.yaml` | Declarative benchmark scenarios targeting distinct reliability failure modes. |

## Execution Lifecycle

1. **Workspace Initialization & Reset**: `MockMCPWorkspace.reset(scenario.initial_state)` restores a clean baseline state before each run so mutations never leak between seeds or modes.
2. **Pre-Call Guardrail Checks (`hardened` mode)**: `LoopBreaker` verifies call counts, retry caps, duplicate signatures, and elapsed time budgets before invoking a tool, while `IdempotencyGuard` detects duplicate mutation keys.
3. **Fault Dispatch**: Matching `FaultConfig` rules in `scenario.fault_profile` are evaluated deterministically for the active step, tool, and seed.
4. **Tool Execution & Post-Response Guardrails**: Mock MCP tools execute against the workspace. In `hardened` mode, `validate_and_normalize_payload` repairs known key aliases or triggers a safe fallback payload when schema violations occur, and `IdempotencyGuard` records state deltas for potential rollback.
5. **Invariant Evaluation & Reporting**: At run completion, `evaluate_invariants` checks all declared `InvariantSpec` rules and produces a `RunResult` with full `TraceEvent` history.
