from server.services.auth_runtime.orchestrators.cli_delegate_orchestrator import CliDelegateOrchestrator


class _ManagerStub:
    def start_session(self, **kwargs):
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


def test_cli_delegate_orchestrator_start():
    orchestrator = CliDelegateOrchestrator(_ManagerStub())
    started = orchestrator.start_session(
        engine="gemini",
        auth_method="auth_code_or_url",
        provider_id=None,
        callback_base_url="http://localhost:8000",
    )
    assert started["transport"] == "cli_delegate"
    assert started["orchestrator"] == "cli_delegate_orchestrator"
    assert started["transport_state_machine"] == "cli_delegate_v1"
