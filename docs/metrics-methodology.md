# Evaluation Metrics and Benchmark Methodology

To support objective comparisons across configurations and conference benchmarks, `mcp-drift-lab` evaluates every scenario across matched seeds and execution modes (`baseline` vs. `hardened`).

## Core Run Metrics (`RunResult`)

- **Task Completion (`task_completed`)**: Indicates whether the execution plan completed without a terminating error or budget cutoff.
- **Invariant Pass Rate (`invariant_pass_rate`)**: The fraction of runs in which all scenario-defined `InvariantSpec` rules evaluate to `true`. This is the primary reliability metric because it captures safety and state integrity alongside task progress.
- **Clean State Rate (`clean_state_rate`)**: The fraction of runs concluding with zero uncompensated state mutations (`final_state_clean == True`).
- **Tool Calls & Retries (`tool_calls_count`, `retry_count`)**: Measures execution overhead and retry amplification under fault injection.
- **Guardrail Interventions (`guardrail_interventions`)**: Counts how often schema normalization/fallback, loop breaking, or idempotency deduplication/rollback intervened during a run.
- **Latency (`total_latency_ms`, `avg_latency_ms`)**: Tracks end-to-end execution duration across steps, including injected fault delays and sleep simulation when enabled.

## Paired Baseline vs. Hardened Comparison

For each scenario $S$ and deterministic seed set $K$:

1. Execute `run_scenario(S, mode=BASELINE, seed=k)` for each $k \in K$.
2. Execute `run_scenario(S, mode=HARDENED, seed=k)` for each $k \in K$ using the identical scenario definition and seed.
3. Compare aggregate metrics from `summarize_results(...)`:
   - **Reliability Lift**: $\Delta \text{Invariant Pass Rate} = \text{PassRate}_{\text{hardened}} - \text{PassRate}_{\text{baseline}}$.
   - **State Integrity Lift**: $\Delta \text{Clean State Rate} = \text{CleanStateRate}_{\text{hardened}} - \text{CleanStateRate}_{\text{baseline}}$.
   - **Overhead Trade-off**: Compare `avg_latency_ms`, `tool_calls_count`, and `guardrail_interventions` to verify that safety gains do not introduce runaway loops or excessive latency.

## CI Evaluation Gate

In `.github/workflows/eval-gate.yml`, `mcp-drift run` executes scenarios across deterministic seeds (`42`, `101`), exports JSONL traces and `summary.json` / `summary.md` artifacts, and can enforce `--min-hardened-pass-rate` to block regressions on pull requests.
