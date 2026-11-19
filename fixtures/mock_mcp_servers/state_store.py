from __future__ import annotations

from copy import deepcopy
from typing import Any


class MockMCPWorkspace:
    """Deterministic in-memory environment shared by mock MCP tools during a single run."""

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        self._initial_state: dict[str, Any] = deepcopy(initial_state) if initial_state else {
            "services": {
                "payments-api": {"status": "healthy", "latency_ms": 42, "error_rate": 0.002},
                "auth-service": {"status": "degraded", "latency_ms": 310, "error_rate": 0.045},
            },
            "feature_flags": {
                "strict_rate_limit": False,
                "circuit_breaker_v2": False,
            },
            "incidents": [],
        }
        self.state: dict[str, Any] = deepcopy(self._initial_state)
        self.mutations: list[dict[str, Any]] = []

    def reset(self, initial_state: dict[str, Any] | None = None) -> None:
        """Reset workspace state and mutation history to guarantee run isolation."""
        if initial_state is not None:
            self._initial_state = deepcopy(initial_state)
        self.state = deepcopy(self._initial_state)
        self.mutations.clear()

    def record_mutation(self, action: str, target: str, before: Any, after: Any) -> None:
        self.mutations.append(
            {
                "action": action,
                "target": target,
                "before": deepcopy(before),
                "after": deepcopy(after),
            }
        )
