from fixtures.mock_mcp_servers.config_store import ConfigStoreMockServer
from fixtures.mock_mcp_servers.state_store import MockMCPWorkspace


def test_workspace_reset_clears_mutated_flags_and_incidents() -> None:
    workspace = MockMCPWorkspace()
    server = ConfigStoreMockServer(workspace)

    # Mutate a feature flag and append an incident note
    flag_res = server.update_config_flag("strict_rate_limit", True)
    inc_res = server.create_incident_note(
        title="Elevated latency on auth-service",
        severity="high",
        summary="Observed p95 latency spike during fault test.",
    )

    assert flag_res["ok"] is True
    assert workspace.state["feature_flags"]["strict_rate_limit"] is True
    assert inc_res["ok"] is True
    assert len(workspace.state["incidents"]) == 1
    assert len(workspace.mutations) == 2

    # Reset workspace between runs and verify clean baseline state
    server.reset()

    assert workspace.state["feature_flags"]["strict_rate_limit"] is False
    assert workspace.state["incidents"] == []
    assert workspace.mutations == []
