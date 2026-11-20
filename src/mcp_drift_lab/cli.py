from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from mcp_drift_lab.models import ExecutionMode, RunResult, Scenario
from mcp_drift_lab.reporting import (
    format_markdown_summary,
    summarize_results,
    write_run_result_json,
    write_traces_jsonl,
)
from mcp_drift_lab.runner import run_scenario


def load_scenarios(path: str | Path) -> list[Scenario]:
    """Load one or more Scenario definitions from a YAML or JSON file or directory."""
    target = Path(path)
    files: list[Path] = []
    if target.is_dir():
        files = sorted(
            [p for p in target.iterdir() if p.suffix.lower() in {".yaml", ".yml", ".json"}]
        )
    elif target.is_file():
        files = [target]
    else:
        raise FileNotFoundError(f"Scenario path not found: {target}")

    scenarios: list[Scenario] = []
    for file_path in files:
        raw_text = file_path.read_text(encoding="utf-8")
        data: Any = (
            json.loads(raw_text)
            if file_path.suffix.lower() == ".json"
            else yaml.safe_load(raw_text)
        )
        if isinstance(data, list):
            for item in data:
                scenarios.append(Scenario.model_validate(item))
        elif isinstance(data, dict):
            scenarios.append(Scenario.model_validate(data))
        else:
            raise ValueError(f"Unsupported scenario structure in {file_path}")
    return scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-drift",
        description="Deterministic fault-injection and reliability harness for MCP toolchains.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_cmd = subparsers.add_parser("run", help="Execute scenarios and generate evaluation reports.")
    run_cmd.add_argument(
        "--scenarios",
        default="scenarios",
        help="Path to a scenario file or directory (default: scenarios).",
    )
    run_cmd.add_argument(
        "--modes",
        nargs="+",
        choices=[m.value for m in ExecutionMode],
        default=[ExecutionMode.BASELINE.value, ExecutionMode.HARDENED.value],
        help="Execution modes to evaluate.",
    )
    run_cmd.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=[42, 101],
        help="Deterministic seeds to run per scenario and mode.",
    )
    run_cmd.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory to write traces, results, and summary reports (default: artifacts).",
    )
    run_cmd.add_argument(
        "--min-hardened-pass-rate",
        type=float,
        default=None,
        help="Optional CI threshold (0.0-1.0) for hardened mode invariant pass rate.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        scenarios = load_scenarios(args.scenarios)
        if not scenarios:
            print("No scenarios found to execute.", file=sys.stderr)
            return 2

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        all_results: list[RunResult] = []

        for scenario in scenarios:
            for mode_str in args.modes:
                mode = ExecutionMode(mode_str)
                for seed in args.seeds:
                    result = run_scenario(scenario, mode=mode, seed=seed)
                    all_results.append(result)
                    write_run_result_json(
                        result, output_dir / "runs" / f"{result.run_id}.json"
                    )
                    write_traces_jsonl(
                        result.traces, output_dir / "traces" / f"{result.run_id}.jsonl"
                    )

        summary = summarize_results(all_results)
        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        markdown_report = format_markdown_summary(summary)
        (output_dir / "summary.md").write_text(markdown_report, encoding="utf-8")
        print(markdown_report)

        if args.min_hardened_pass_rate is not None:
            hardened_runs = [r for r in all_results if r.mode == ExecutionMode.HARDENED]
            pass_rate = (
                sum(1 for r in hardened_runs if r.invariants_passed) / len(hardened_runs)
                if hardened_runs
                else 0.0
            )
            if pass_rate < args.min_hardened_pass_rate:
                print(
                    f"Gate failed: hardened invariant pass rate {pass_rate:.1%} < "
                    f"{args.min_hardened_pass_rate:.1%}",
                    file=sys.stderr,
                )
                return 1

        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
