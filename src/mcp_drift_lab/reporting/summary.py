from __future__ import annotations

from collections import defaultdict
from typing import Any

from mcp_drift_lab.models import RunResult


def summarize_results(results: list[RunResult]) -> dict[str, Any]:
    """Compute aggregate reliability metrics grouped by scenario and execution mode."""
    grouped: dict[tuple[str, str], list[RunResult]] = defaultdict(list)
    for r in results:
        grouped[(r.scenario_id, r.mode.value)].append(r)

    rows: list[dict[str, Any]] = []
    for (scenario_id, mode), runs in sorted(grouped.items()):
        count = len(runs)
        completed = sum(1 for r in runs if r.task_completed)
        inv_passed = sum(1 for r in runs if r.invariants_passed)
        clean_state = sum(1 for r in runs if r.final_state_clean)
        avg_latency = round(sum(r.total_latency_ms for r in runs) / count, 3)
        total_guardrails = sum(r.guardrail_interventions for r in runs)
        total_retries = sum(r.retry_count for r in runs)

        rows.append(
            {
                "scenario_id": scenario_id,
                "mode": mode,
                "runs": count,
                "task_completion_rate": round(completed / count, 4),
                "invariant_pass_rate": round(inv_passed / count, 4),
                "clean_state_rate": round(clean_state / count, 4),
                "avg_latency_ms": avg_latency,
                "total_guardrail_interventions": total_guardrails,
                "total_retries": total_retries,
            }
        )

    overall_runs = len(results)
    overall_inv_rate = (
        round(sum(1 for r in results if r.invariants_passed) / overall_runs, 4)
        if overall_runs > 0
        else 0.0
    )

    return {
        "total_runs": overall_runs,
        "overall_invariant_pass_rate": overall_inv_rate,
        "by_scenario_mode": rows,
    }


def format_markdown_summary(summary: dict[str, Any]) -> str:
    """Render a summary dictionary as a clean Markdown table without emojis."""
    lines = [
        "# MCP Drift Lab Evaluation Summary",
        "",
        f"- **Total Runs**: {summary.get('total_runs', 0)}",
        f"- **Overall Invariant Pass Rate**: {summary.get('overall_invariant_pass_rate', 0.0):.1%}",
        "",
        "| Scenario | Mode | Runs | Completion | Invariants | Clean State | Avg Latency (ms) | Guardrails |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.get("by_scenario_mode", []):
        lines.append(
            f"| {row['scenario_id']} | {row['mode']} | {row['runs']} | "
            f"{row['task_completion_rate']:.1%} | {row['invariant_pass_rate']:.1%} | "
            f"{row['clean_state_rate']:.1%} | {row['avg_latency_ms']:.1f} | "
            f"{row['total_guardrail_interventions']} |"
        )
    return "\n".join(lines)
