from pathlib import Path

from mcp_drift_lab.cli import load_scenarios, main as cli_main
from mcp_drift_lab.models import ExecutionMode
from mcp_drift_lab.reporting import (
    format_markdown_summary,
    read_traces_jsonl,
    summarize_results,
    write_traces_jsonl,
)
from mcp_drift_lab.runner import run_scenario


def test_scenario_runs_are_deterministic_for_same_seed() -> None:
    scenarios = load_scenarios("scenarios")
    assert len(scenarios) >= 2
    scenario = scenarios[0]

    run_a = run_scenario(scenario, mode=ExecutionMode.HARDENED, seed=42)
    run_b = run_scenario(scenario, mode=ExecutionMode.HARDENED, seed=42)

    assert run_a.invariants_passed is run_b.invariants_passed
    assert run_a.tool_calls_count == run_b.tool_calls_count
    assert run_a.guardrail_interventions == run_b.guardrail_interventions
    assert run_a.final_state == run_b.final_state


def test_trace_roundtrip_and_summary_report(tmp_path: Path) -> None:
    scenarios = load_scenarios("scenarios")
    results = []
    for scenario in scenarios:
        for mode in (ExecutionMode.BASELINE, ExecutionMode.HARDENED):
            res = run_scenario(scenario, mode=mode, seed=42)
            results.append(res)
            trace_file = tmp_path / f"{res.run_id}.jsonl"
            write_traces_jsonl(res.traces, trace_file)
            loaded = read_traces_jsonl(trace_file)
            assert len(loaded) == len(res.traces)

    summary = summarize_results(results)
    assert summary["total_runs"] == len(results)
    md = format_markdown_summary(summary)
    assert "# MCP Drift Lab Evaluation Summary" in md


def test_cli_run_generates_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "artifacts"
    exit_code = cli_main(
        [
            "run",
            "--scenarios",
            "scenarios",
            "--modes",
            "baseline",
            "hardened",
            "--seeds",
            "42",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert exit_code == 0
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "summary.md").exists()
