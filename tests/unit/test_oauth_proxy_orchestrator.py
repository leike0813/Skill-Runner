from server.services.auth_runtime.orchestrators.oauth_proxy_orchestrator import OAuthProxyOrchestrator


class _ManagerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def start_session(self, **kwargs):
        self.calls.append(("start", kwargs))
        return {
            "session_id": "s1",
            "engine": kwargs["engine"],
            "transport": "oauth_proxy",
            "auth_method": kwargs["auth_method"],
            "status": "waiting_user",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:01Z",
            "expires_at": "2026-02-27T00:15:00Z",
            "auth_ready": False,
            "terminal": False,
        }

    def get_session(self, session_id):
        return {
            "session_id": session_id,
            "engine": "codex",
            "transport": "oauth_proxy",
            "auth_method": "callback",
            "status": "waiting_user",
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

    def complete_openai_callback(self, **kwargs):
        payload = self.get_session("s1")
        payload["status"] = "succeeded"
        payload["terminal"] = True
        return payload


def test_oauth_proxy_orchestrator_start_and_get():
    mgr = _ManagerStub()
    orchestrator = OAuthProxyOrchestrator(mgr)
    started = orchestrator.start_session(
        engine="codex",
        auth_method="callback",
        provider_id=None,
        callback_base_url="http://localhost:8000",
    )
    assert started["orchestrator"] == "oauth_proxy_orchestrator"
    assert started["transport_state_machine"] == "oauth_proxy_v1"
    got = orchestrator.get_session("s1")
    assert got["transport"] == "oauth_proxy"


def test_oauth_proxy_orchestrator_gemini_maps_to_auth():
    mgr = _ManagerStub()
    orchestrator = OAuthProxyOrchestrator(mgr)
    started = orchestrator.start_session(
        engine="gemini",
        auth_method="callback",
        provider_id=None,
        callback_base_url=None,
    )
    assert started["engine"] == "gemini"
    assert mgr.calls[-1][1]["method"] == "auth"


def test_oauth_proxy_orchestrator_iflow_maps_to_auth():
    mgr = _ManagerStub()
    orchestrator = OAuthProxyOrchestrator(mgr)
    started = orchestrator.start_session(
        engine="iflow",
        auth_method="callback",
        provider_id=None,
        callback_base_url=None,
    )
    assert started["engine"] == "iflow"
    assert mgr.calls[-1][1]["method"] == "auth"
