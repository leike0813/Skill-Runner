from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from server.engines.qwen.auth.protocol.coding_plan_flow import CodingPlanAuthFlow


def test_qwen_coding_plan_flow_writes_snapshot_backed_settings(tmp_path: Path, monkeypatch) -> None:
    flow = CodingPlanAuthFlow(tmp_path)
    settings_path = tmp_path / ".qwen" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "modelProviders": {
                    "openai": [
                        {
                            "id": "legacy-coding-plan",
                            "name": "legacy",
                            "baseUrl": "https://coding.dashscope.aliyuncs.com/v1",
                            "envKey": "BAILIAN_CODING_PLAN_API_KEY",
                        },
                        {
                            "id": "custom-provider",
                            "name": "custom",
                            "baseUrl": "https://example.com/v1",
                            "envKey": "CUSTOM_API_KEY",
                        },
                    ]
                },
                "codingPlan": {"region": "china", "version": "old-version"},
            }
        ),
        encoding="utf-8",
    )
    snapshot_file = Path("server/engines/qwen/models/models_0.14.0.json").resolve()
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry.get_models",
        lambda engine, refresh=True: SimpleNamespace(snapshot_version_used="0.14.0"),
    )
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry._load_manifest",
        lambda engine: {"engine": "qwen", "snapshots": [{"version": "0.14.0", "file": snapshot_file.name}]},
    )
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry._snapshot_file",
        lambda manifest, version: snapshot_file,
    )

    runtime = flow.start_session(session_id="auth-1", provider_id="coding-plan-china")
    flow.complete_api_key(runtime, "sk-sp-123")

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    openai_models = payload["modelProviders"]["openai"]
    assert openai_models[0]["id"] == "qwen3.5-plus"
    assert openai_models[0]["name"] == "[ModelStudio Coding Plan] qwen3.5-plus"
    assert openai_models[0]["generationConfig"]["contextWindowSize"] == 1000000
    assert openai_models[4]["id"] == "qwen3-coder-plus"
    assert openai_models[4]["generationConfig"] == {"contextWindowSize": 1000000}
    assert openai_models[-1]["id"] == "custom-provider"
    assert payload["env"]["BAILIAN_CODING_PLAN_API_KEY"] == "sk-sp-123"
    assert payload["codingPlan"] == {"region": "china"}
    assert payload["model"]["name"] == "qwen3.5-plus"


def test_qwen_coding_plan_flow_global_uses_official_intl_endpoint(tmp_path: Path, monkeypatch) -> None:
    flow = CodingPlanAuthFlow(tmp_path)
    snapshot_file = Path("server/engines/qwen/models/models_0.14.0.json").resolve()
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry.get_models",
        lambda engine, refresh=True: SimpleNamespace(snapshot_version_used="0.14.0"),
    )
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry._load_manifest",
        lambda engine: {"engine": "qwen", "snapshots": [{"version": "0.14.0", "file": snapshot_file.name}]},
    )
    monkeypatch.setattr(
        "server.engines.qwen.auth.protocol.coding_plan_flow.model_registry._snapshot_file",
        lambda manifest, version: snapshot_file,
    )

    runtime = flow.start_session(session_id="auth-2", provider_id="coding-plan-global")
    flow.complete_api_key(runtime, "sk-sp-456")

    payload = json.loads((tmp_path / ".qwen" / "settings.json").read_text(encoding="utf-8"))
    openai_models = payload["modelProviders"]["openai"]
    assert openai_models[0]["baseUrl"] == "https://coding-intl.dashscope.aliyuncs.com/v1"
    assert openai_models[0]["name"] == "[ModelStudio Coding Plan for Global/Intl] qwen3.5-plus"
    assert payload["codingPlan"] == {"region": "global"}
