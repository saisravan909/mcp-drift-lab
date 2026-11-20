from __future__ import annotations

import json
from pathlib import Path

from mcp_drift_lab.models import RunResult, TraceEvent


def write_traces_jsonl(traces: list[TraceEvent], output_path: str | Path) -> Path:
    """Serialize TraceEvent items to JSON Lines format."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for event in traces:
            fh.write(event.model_dump_json() + "\n")
    return path


def read_traces_jsonl(input_path: str | Path) -> list[TraceEvent]:
    """Load TraceEvent items from a JSON Lines file."""
    path = Path(input_path)
    events: list[TraceEvent] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                events.append(TraceEvent.model_validate_json(stripped))
    return events


def write_run_result_json(result: RunResult, output_path: str | Path) -> Path:
    """Serialize a RunResult object to formatted JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
