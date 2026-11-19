from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def _signature(tool_name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class LoopBreaker:
    """Enforces call budgets, retry caps, duplicate-call loop limits, and latency budgets."""

    max_tool_calls: int = 12
    max_retries_per_tool: int = 2
    max_duplicate_calls: int = 2
    max_elapsed_ms: float = 10_000.0

    total_calls: int = 0
    elapsed_ms: float = 0.0
    retries_by_tool: dict[str, int] = field(default_factory=dict)
    seen_signatures: dict[str, int] = field(default_factory=dict)

    def check_before_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        is_retry: bool = False,
        step_elapsed_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Evaluate whether a tool call or retry is allowed under current budget limits."""
        projected_calls = self.total_calls + 1
        projected_elapsed = self.elapsed_ms + max(0.0, step_elapsed_ms)
        sig = _signature(tool_name, arguments)
        duplicate_count = self.seen_signatures.get(sig, 0) + 1
        retry_count = self.retries_by_tool.get(tool_name, 0) + (1 if is_retry else 0)

        if projected_elapsed > self.max_elapsed_ms:
            return {
                "allowed": False,
                "triggered": True,
                "reason": "elapsed_budget_exceeded",
                "elapsed_ms": projected_elapsed,
                "max_elapsed_ms": self.max_elapsed_ms,
            }

        if projected_calls > self.max_tool_calls:
            return {
                "allowed": False,
                "triggered": True,
                "reason": "max_tool_calls_exceeded",
                "total_calls": projected_calls,
                "max_tool_calls": self.max_tool_calls,
            }

        if is_retry and retry_count > self.max_retries_per_tool:
            return {
                "allowed": False,
                "triggered": True,
                "reason": "max_retries_exceeded",
                "tool_name": tool_name,
                "retry_count": retry_count,
                "max_retries_per_tool": self.max_retries_per_tool,
            }

        if duplicate_count > self.max_duplicate_calls:
            return {
                "allowed": False,
                "triggered": True,
                "reason": "duplicate_call_loop_detected",
                "tool_name": tool_name,
                "duplicate_count": duplicate_count,
                "max_duplicate_calls": self.max_duplicate_calls,
            }

        # Commit budget counters for an allowed call
        self.total_calls = projected_calls
        self.elapsed_ms = projected_elapsed
        self.seen_signatures[sig] = duplicate_count
        if is_retry:
            self.retries_by_tool[tool_name] = retry_count

        return {
            "allowed": True,
            "triggered": False,
            "reason": None,
            "total_calls": self.total_calls,
            "elapsed_ms": self.elapsed_ms,
        }
