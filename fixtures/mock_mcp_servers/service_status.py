from __future__ import annotations

from typing import Any

from .state_store import MockMCPWorkspace


class ServiceStatusMockServer:
    """Mock MCP server exposing read-only telemetry/health inspection tools."""

    def __init__(self, workspace: MockMCPWorkspace) -> None:
        self.workspace = workspace

    def reset(self, initial_state: dict[str, Any] | None = None) -> None:
        self.workspace.reset(initial_state)

    def read_service_health(self, service_name: str) -> dict[str, Any]:
        services = self.workspace.state.get("services", {})
        if service_name not in services:
            return {
                "ok": False,
                "error": f"unknown_service:{service_name}",
                "available_services": sorted(services.keys()),
            }
        svc = services[service_name]
        return {
            "ok": True,
            "service_name": service_name,
            "status": svc["status"],
            "latency_ms": svc["latency_ms"],
            "error_rate": svc["error_rate"],
        }
