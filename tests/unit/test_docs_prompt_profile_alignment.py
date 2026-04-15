from __future__ import annotations

import json
from pathlib import Path

from server.runtime.adapter.common.profile_loader import SessionStrategy


def _load_profile_prompt_template(engine: str) -> str:
    path = Path(f"server/engines/{engine}/adapter/adapter_profile.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompt_builder = payload.get("prompt_builder")
    assert isinstance(prompt_builder, dict)
    template = prompt_builder.get("skill_invoke_line_template")
    assert isinstance(template, str)
    return template


def test_prompt_organization_ssot_engine_mappings_match_profiles() -> None:
    doc_text = Path("docs/prompt_organization_ssot.md").read_text(encoding="utf-8")
    expected_lines = {
        "codex": f"- `codex`: `{_load_profile_prompt_template('codex')}`",
        "claude": f"- `claude`: `{_load_profile_prompt_template('claude')}`",
        "opencode": f"- `opencode`: `{_load_profile_prompt_template('opencode')}`",
        "qwen": f"- `qwen`: `{_load_profile_prompt_template('qwen')}`",
        "gemini": f"- `gemini`: `{_load_profile_prompt_template('gemini')}`",
        "iflow": f"- `iflow`: `{_load_profile_prompt_template('iflow')}`",
    }

    for line in expected_lines.values():
        assert line in doc_text


def test_adapter_profile_reference_session_codec_strategy_enum_matches_loader() -> None:
    doc_text = Path("docs/developer/adapter_profile_reference.md").read_text(encoding="utf-8")
    for strategy in SessionStrategy.__args__:
        assert f'"{strategy}"' in doc_text
    assert '"json_lines_extract"' not in doc_text
    assert '"json_recursive_extract"' not in doc_text
