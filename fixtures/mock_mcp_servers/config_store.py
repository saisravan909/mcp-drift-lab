from __future__ import annotations

from typing import Any

from .state_store import MockMCPWorkspace


class ConfigStoreMockServer:
    """Mock MCP server exposing stateful configuration and incident logging tools."""

    def __init__(self, workspace: MockMCPWorkspace) -> None:
        self.workspace = workspace

    def reset(self, initial_state: dict[str, Any] | None = None) -> None:
        self.workspace.reset(initial_state)

    def update_config_flag(self, flag_name: str, enabled: bool) -> dict[str, Any]:
        flags = self.workspace.state.setdefault("feature_flags", {})
        if flag_name not in flags:
            return {
                "ok": False,
                "error": f"unknown_flag:{flag_name}",
                "available_flags": sorted(flags.keys()),
            }
        previous = flags[flag_name]
        flags[flag_name] = bool(enabled)
        self.workspace.record_mutation(
            action="update_config_flag",
            target=f"feature_flags.{flag_name}",
            before=previous,
            after=flags[flag_name],
        )
        return {
            "ok": True,
            "flag_name": flag_name,
            "previous_value": previous,
            "enabled": flags[flag_name],
        }

    def create_incident_note(self, title: str, severity: str, summary: str) -> dict[str, Any]:
        incidents = self.workspace.state.setdefault("incidents", [])
        incident_id = f"INC-{len(incidents) + 101}"
        record = {
            "id": incident_id,
            "title": title,
            "severity": severity,
            "summary": summary,
        }
        before_count = len(incidents)
        incidents.append(record)
        self.workspace.record_mutation(
            action="create_incident_note",
            target=f"incidents[{before_count}]",
            before=None,
            after=record,
        )
        return {
            "ok": True,
            "incident_id": incident_id,
            "incident": record,
        }
