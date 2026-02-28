from __future__ import annotations

from pathlib import Path

from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.contracts import AdapterExecutionContext


class _ConfigComposer:
    def compose(self, ctx: AdapterExecutionContext) -> Path:
        return ctx.run_dir / "engine.json"


class _WorkspaceProvisioner:
    def prepare(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:
        return config_path.parent / ".workspace"


class _PromptBuilder:
    def render(self, ctx: AdapterExecutionContext) -> str:
        return f"skill={ctx.skill.id}"


class _CommandBuilder:
    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:
        return ["engine", "start", prompt]

    def build_resume(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
        session_handle: EngineSessionHandle,
    ) -> list[str]:
        return ["engine", "resume", prompt, session_handle.handle_value]


class _StreamParser:
    def parse(self, raw_stdout: str) -> dict[str, object]:
        return {"stdout": raw_stdout}


class _SessionCodec:
    def extract(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=f"{turn_index}:{raw_stdout}",
            created_at_turn=turn_index,
        )


def test_engine_execution_adapter_component_contracts() -> None:
    adapter = EngineExecutionAdapter(
        config_composer=_ConfigComposer(),
        workspace_provisioner=_WorkspaceProvisioner(),
        prompt_builder=_PromptBuilder(),
        command_builder=_CommandBuilder(),
        stream_parser=_StreamParser(),
        session_codec=_SessionCodec(),
    )
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="demo-skill"),
        run_dir=Path("/tmp/demo"),
        input_data={"x": 1},
        options={"model": "gpt-5"},
    )
    handle = EngineSessionHandle(
        engine="codex",
        handle_type=EngineSessionHandleType.SESSION_ID,
        handle_value="sid-1",
    )

    assert adapter.build_start_command(ctx) == ["engine", "start", "skill=demo-skill"]
    assert adapter.build_resume_command(ctx, handle) == [
        "engine",
        "resume",
        "skill=demo-skill",
        "sid-1",
    ]
    assert adapter.parse_output("hello") == {"stdout": "hello"}
    assert adapter.extract_session_handle("stream", turn_index=2).handle_value == "2:stream"

    prompt, workspace = adapter.bootstrap(ctx)
    assert prompt == "skill=demo-skill"
    assert workspace == Path("/tmp/demo/.workspace")

    artifacts = adapter.as_artifacts(
        exit_code=0,
        raw_stdout="{}",
        raw_stderr="",
        session_handle=handle,
    )
    assert artifacts.exit_code == 0
    assert artifacts.session_handle is not None

