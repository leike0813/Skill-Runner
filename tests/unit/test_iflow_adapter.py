import json
from pathlib import Path

from server.adapters.iflow_adapter import IFlowAdapter
from server.models import SkillManifest


def test_construct_config_maps_model_and_merges_iflow_config(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    skill = SkillManifest(
        id="test-skill",
        path=tmp_path,
        name="Test Skill",
        description="Test",
        runtime=None,
        entrypoint={}
    )

    adapter = IFlowAdapter()
    options = {
        "model": "gpt-4-test",
        "verbose": True,
        "iflow_config": {"theme": "Dark"}
    }

    config_path = adapter._construct_config(skill, run_dir, options)
    assert config_path.exists()

    args = json.loads(config_path.read_text())
    assert args["modelName"] == "gpt-4-test"
    assert args["theme"] == "Dark"
    assert "verbose" not in args
