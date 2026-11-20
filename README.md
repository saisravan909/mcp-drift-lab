# mcp-drift-lab

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI: Eval Gate](https://img.shields.io/badge/CI-Eval%20Gate-informational.svg)](.github/workflows/eval-gate.yml)
[![Framework: Pydantic v2](https://img.shields.io/badge/Pydantic-v2-teal.svg)](https://docs.pydantic.dev/)

**Deterministic fault-injection and reliability harness for Model Context Protocol (MCP) servers and agent toolchains.**

`mcp-drift-lab` helps engineering teams, platform builders, and reliability researchers test how AI agent toolchains behave when upstream tools drift, slow down, fail transiently, or leave partial state changes behind. Instead of relying on one-off demos or brittle live environments, every run executes deterministically from a seed and compares `baseline` (unmitigated) behavior against `hardened` (guardrail-enforced) behavior.

---

## Why This Matters for Evaluators and Reliability Teams

Real-world tool integrations rarely fail in clean, textbook ways. A tool renames a field, drops a required status key, introduces tail latency, returns `503` on the first attempt, or errors out after mutating state in an earlier step.

`mcp-drift-lab` makes those failure modes repeatable, measurable, and inspectable:

- **Seeded Determinism**: Re-run the exact same scenario and seed across commits, guardrail policies, or model/toolchain changes to get consistent, auditable results.
- **Paired Baseline vs. Hardened Benchmarks**: Evaluate identical runs with guardrails off (`baseline`) and on (`hardened`) to quantify reliability lift, state safety, and latency/call overhead.
- **Invariant-First Verification**: Separate surface task completion from system safety using explicit invariant checks (`max_retries`, `max_tool_calls`, `no_uncompensated_mutations`, `allowed_tools_only`, `required_tools_called`, and `state_equals`).
- **Cloud & CI Ready**: Designed to run smoothly in cloud sandboxes or GitHub Actions (`eval-gate.yml`) without requiring a local Python installation on your laptop.

---

## Execution & Evaluation Flow

```mermaid
flowchart LR
    A["Scenario YAML / JSON\n+ Seed + Mode"] --> B["Mock MCP Workspace\n(Clean Reset per Run)"]
    B --> C{"Hardened Mode?\nLoopBreaker & Dedup"}
    C -- "Blocked / Dup" --> G["Guardrail Trace\n& Early Stop"]
    C -- "Allowed" --> D["Fault Injector\n(Drift, Latency, 503, State)"]
    D --> E["Mock MCP Tools\n& State Mutations"]
    E --> F{"Hardened Mode?\nSchemaGuard & Rollback"}
    F --> H["Invariant Engine\n& RunResult"]
    H --> I["JSONL Traces +\nsummary.json / summary.md"]# mcp-drift-lab
