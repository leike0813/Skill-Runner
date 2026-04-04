import json
from pathlib import Path

from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.models import SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_qwen_config_composer_merges_default_skill_runtime_and_enforced(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "qwen_config.json").write_text(
        json.dumps(
            {
                "model": {"name": "qwen3.6-plus"},
                "env": {"SOURCE": "skill"},
                "tools": {"sandbox": True},
            }
        ),
        encoding="utf-8",
    )

    adapter = QwenExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill", path=skill_dir),
        run_dir=run_dir,
        input_data={},
        options={
            "model": "qwen3-coder-plus",
            "qwen_config": {
                "env": {"SOURCE": "runtime", "EXTRA": "runtime"},
                "tools": {"sandbox": True},
                "permissions": {"defaultMode": "custom"},
            },
        },
    )

    config_path = adapter.config_composer.compose(ctx)
    payload = _read_json(config_path)

    assert payload["model"]["name"] == "qwen3-coder-plus"
    assert payload["env"]["SOURCE"] == "runtime"
    assert payload["env"]["EXTRA"] == "runtime"
    assert payload["output"]["format"] == "stream-json"
    assert payload["tools"]["approvalMode"] == "yolo"
    assert payload["tools"]["sandbox"] is False
    assert payload["permissions"]["defaultMode"] == "bypassPermissions"
