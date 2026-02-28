from server.runtime.auth.orchestrators.cli_delegate import CliDelegateOrchestrator


class _ManagerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def start_session(self, **kwargs):
        self.calls.append(("start", kwargs))
        return {
            "session_id": "s2",
            "engine": kwargs["engine"],
            "transport": "cli_delegate",
            "auth_method": kwargs["auth_method"],
            "status": "waiting_orchestrator",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:01Z",
            "expires_at": "2026-02-27T00:15:00Z",
            "auth_ready": False,
            "terminal": False,
        }

    def get_session(self, session_id):
        return {
            "session_id": session_id,
            "engine": "gemini",
            "transport": "cli_delegate",
            "auth_method": "auth_code_or_url",
            "status": "waiting_orchestrator",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:01Z",
            "expires_at": "2026-02-27T00:15:00Z",
            "auth_ready": False,
            "terminal": False,
        }

    def input_session(self, session_id, kind, value):
        return self.get_session(session_id)

    def cancel_session(self, session_id):
        payload = self.get_session(session_id)
        payload["status"] = "canceled"
        payload["terminal"] = True
        return payload

    def resolve_transport_start_method(self, **kwargs):
        self.calls.append(("resolve_method", kwargs))
        if kwargs.get("engine") == "iflow":
            return "iflow-cli-oauth"
        return "auth"


def test_cli_delegate_orchestrator_start():
    manager = _ManagerStub()
    orchestrator = CliDelegateOrchestrator(manager)
    started = orchestrator.start_session(
        engine="gemini",
        auth_method="auth_code_or_url",
        provider_id=None,
        callback_base_url="http://localhost:8000",
    )
    assert started["transport"] == "cli_delegate"
    assert started["orchestrator"] == "cli_delegate_orchestrator"
    assert started["transport_state_machine"] == "cli_delegate_v1"
    assert manager.calls[-1][0] == "start"
    assert manager.calls[-1][1]["method"] == "auth"
