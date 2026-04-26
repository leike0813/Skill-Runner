from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema  # type: ignore[import-untyped]
import pytest
import tomlkit

from server.engines.codex.adapter.command_builder import CodexCommandBuilder
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.codex.adapter.toml_manager import CodexConfigManager
from server.engines.claude.adapter.mcp_materializer import (
    cleanup_claude_run_local_mcp,
    materialize_claude_mcp_resolution,
    sync_claude_agent_home_mcp,
)
from server.engines.claude.adapter.state_paths import active_claude_state_path
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.models import SkillManifest, SkillMcpDeclaration
from server.services.mcp import (
    McpAuthEnvRef,
    McpAuthHeaderRef,
    McpConfigError,
    McpResolution,
    McpServerDefinition,
    McpSecretStore,
    ResolvedMcpServer,
    codex_run_profile_name,
    load_mcp_registry_payload,
    load_mcp_registry,
    render_mcp_config,
    resolve_mcp_servers,
    validate_no_mcp_root_keys,
    write_runtime_mcp_registry_payload,
)


def _stdio_server(
    server_id: str,
    *,
    activation: str = "declared",
    engines: tuple[str, ...] = ("codex", "gemini", "qwen", "claude", "opencode"),
    scope: str = "run-local",
) -> McpServerDefinition:
    return McpServerDefinition(
        id=server_id,
        activation=activation,  # type: ignore[arg-type]
        effective_engines=engines,
        scope=scope,  # type: ignore[arg-type]
        transport="stdio",
        command="python",
        args=("-m", server_id),
    )


def _registry_schema() -> dict[str, object]:
    schema_path = Path("server/contracts/schemas/mcp_registry.schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _manifest_schema() -> dict[str, object]:
    schema_path = Path("server/contracts/schemas/skill/skill_runner_manifest.schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _minimal_runner(**overrides: object) -> dict[str, object]:
    runner: dict[str, object] = {
        "id": "demo-skill",
        "execution_modes": ["auto"],
    }
    runner.update(overrides)
    return runner


def _skill_with_mcp(*server_ids: str) -> SkillManifest:
    return SkillManifest(
        id="demo-skill",
        mcp=SkillMcpDeclaration(required_servers=list(server_ids)),
    )


def test_mcp_registry_schema_accepts_stdio_server() -> None:
    payload = {
        "version": 1,
        "servers": {
            "demo": {
                "activation": "default",
                "engines": ["codex"],
                "unsupported_engines": ["gemini"],
                "scope": "agent-home",
                "transport": "stdio",
                "command": "python",
                "args": ["-m", "demo"],
            }
        },
    }

    jsonschema.validate(instance=payload, schema=_registry_schema())


def test_mcp_registry_schema_accepts_structured_auth_refs() -> None:
    payload = {
        "version": 1,
        "servers": {
            "demo": {
                "activation": "default",
                "scope": "run-local",
                "transport": "stdio",
                "command": "python",
                "auth": {
                    "env": [{"name": "API_KEY", "secret_id": "mcp.demo.env.API_KEY"}],
                    "headers": [
                        {
                            "name": "Authorization",
                            "prefix": "Bearer ",
                            "secret_id": "mcp.demo.header.Authorization",
                        }
                    ],
                },
            }
        },
    }

    jsonschema.validate(instance=payload, schema=_registry_schema())


@pytest.mark.parametrize("field", ["env", "headers", "bearer_token", "secret_ref"])
def test_mcp_registry_schema_rejects_secret_bearing_fields(field: str) -> None:
    payload = {
        "version": 1,
        "servers": {
            "demo": {
                "activation": "default",
                "scope": "run-local",
                "transport": "stdio",
                "command": "python",
                field: {},
            }
        },
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=_registry_schema())


@pytest.mark.parametrize(
    "auth_payload",
    [
        {"env": [{"name": "API_KEY", "value": "raw"}]},
        {"headers": [{"name": "Authorization", "value": "raw"}]},
        {"headers": [{"name": "Authorization", "secret_id": "x", "value": "raw"}]},
    ],
)
def test_mcp_registry_schema_rejects_raw_auth_values(auth_payload: dict[str, object]) -> None:
    payload = {
        "version": 1,
        "servers": {
            "demo": {
                "activation": "default",
                "scope": "run-local",
                "transport": "stdio",
                "command": "python",
                "auth": auth_payload,
            }
        },
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=_registry_schema())


def test_mcp_registry_loader_validates_and_computes_effective_engines(tmp_path: Path) -> None:
    registry_path = tmp_path / "mcp_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "servers": {
                    "demo": {
                        "activation": "default",
                        "unsupported_engines": ["gemini"],
                        "scope": "run-local",
                        "transport": "stdio",
                        "command": "python",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    registry = load_mcp_registry(registry_path)

    assert "demo" in registry
    assert "gemini" not in registry["demo"].effective_engines
    assert "codex" in registry["demo"].effective_engines


def test_runtime_registry_recovers_invalid_json(tmp_path: Path) -> None:
    registry_path = tmp_path / "mcp_registry.json"
    registry_path.write_text("{bad json", encoding="utf-8")

    payload = load_mcp_registry_payload(registry_path)

    assert payload == {"version": 1, "servers": {}}
    assert (tmp_path / "mcp_registry.json.invalid.bak").exists()


def test_runtime_registry_atomic_write_and_reload(tmp_path: Path) -> None:
    registry_path = tmp_path / "mcp_registry.json"
    payload = {
        "version": 1,
        "servers": {
            "demo": {
                "activation": "default",
                "scope": "run-local",
                "transport": "stdio",
                "command": "python",
            }
        },
    }

    write_runtime_mcp_registry_payload(payload, registry_path=registry_path)

    assert json.loads(registry_path.read_text(encoding="utf-8"))["servers"]["demo"]["command"] == "python"
    assert load_mcp_registry(registry_path)["demo"].command == "python"


def test_skill_manifest_schema_accepts_required_mcp_servers() -> None:
    jsonschema.validate(
        instance=_minimal_runner(mcp={"required_servers": ["filesystem", "memory"]}),
        schema=_manifest_schema(),
    )


@pytest.mark.parametrize(
    "mcp_payload",
    [
        {"required_servers": ["filesystem", "filesystem"]},
        {"required_servers": [""]},
        {"servers": {"demo": {"command": "python"}}},
        {"required_servers": ["filesystem"], "env": {"A": "B"}},
    ],
)
def test_skill_manifest_schema_rejects_invalid_mcp_payload(mcp_payload: dict[str, object]) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_minimal_runner(mcp=mcp_payload), schema=_manifest_schema())


def test_resolver_applies_default_and_declared_engine_filtering() -> None:
    registry = {
        "default-codex": _stdio_server(
            "default-codex",
            activation="default",
            engines=("codex",),
        ),
        "declared-gemini": _stdio_server(
            "declared-gemini",
            activation="declared",
            engines=("gemini",),
        ),
    }
    skill = _skill_with_mcp("declared-gemini")

    gemini = resolve_mcp_servers(skill=skill, engine="gemini", registry=registry)
    codex = resolve_mcp_servers(skill=SkillManifest(id="demo-skill"), engine="codex", registry=registry)

    assert [server.definition.id for server in gemini.servers] == ["declared-gemini"]
    assert [server.definition.id for server in codex.servers] == ["default-codex"]


def test_resolver_rejects_unknown_and_engine_incompatible_mcp() -> None:
    registry = {
        "declared-codex": _stdio_server(
            "declared-codex",
            activation="declared",
            engines=("codex",),
        )
    }

    with pytest.raises(McpConfigError, match="unknown MCP server"):
        resolve_mcp_servers(
            skill=_skill_with_mcp("missing"),
            engine="codex",
            registry=registry,
        )

    with pytest.raises(McpConfigError, match="does not support engine 'gemini'"):
        resolve_mcp_servers(
            skill=_skill_with_mcp("declared-codex"),
            engine="gemini",
            registry=registry,
        )


def test_resolver_rejects_skill_requesting_default_mcp() -> None:
    registry = {
        "default-codex": _stdio_server(
            "default-codex",
            activation="default",
            engines=("codex",),
        )
    }

    with pytest.raises(McpConfigError, match="may only require declared"):
        resolve_mcp_servers(
            skill=_skill_with_mcp("default-codex"),
            engine="codex",
            registry=registry,
        )


def test_declared_mcp_is_forced_run_local() -> None:
    registry = {
        "declared": _stdio_server(
            "declared",
            activation="declared",
            engines=("codex",),
            scope="agent-home",
        )
    }

    resolution = resolve_mcp_servers(
        skill=_skill_with_mcp("declared"),
        engine="codex",
        registry=registry,
    )

    assert resolution.servers[0].scope == "run-local"


@pytest.mark.parametrize(
    ("engine", "root"),
    [
        ("codex", "mcp_servers"),
        ("gemini", "mcpServers"),
        ("qwen", "mcpServers"),
        ("claude", "mcpServers"),
        ("opencode", "mcp"),
    ],
)
def test_renderer_maps_engine_roots(engine: str, root: str) -> None:
    server = ResolvedMcpServer(definition=_stdio_server("demo"), scope="run-local")

    rendered = render_mcp_config(engine, (server,))

    assert set(rendered) == {root}
    assert rendered[root]["demo"] == {"command": "python", "args": ["-m", "demo"]}


def test_renderer_injects_stdio_env_secret() -> None:
    server = ResolvedMcpServer(
        definition=McpServerDefinition(
            id="demo",
            activation="declared",
            effective_engines=("codex",),
            scope="run-local",
            transport="stdio",
            command="python",
            auth_env=(McpAuthEnvRef(name="API_KEY", secret_id="secret-1"),),
        ),
        scope="run-local",
    )

    rendered = render_mcp_config("codex", (server,), secret_resolver=lambda secret_id: "raw-key")

    assert rendered["mcp_servers"]["demo"]["env"] == {"API_KEY": "raw-key"}


@pytest.mark.parametrize(
    ("engine", "header_key"),
    [
        ("codex", "http_headers"),
        ("gemini", "headers"),
        ("qwen", "headers"),
        ("claude", "headers"),
        ("opencode", "headers"),
    ],
)
def test_renderer_injects_http_header_secret(engine: str, header_key: str) -> None:
    server = ResolvedMcpServer(
        definition=McpServerDefinition(
            id="demo",
            activation="declared",
            effective_engines=(engine,),
            scope="run-local",
            transport="http",
            url="https://mcp.example/sse",
            auth_headers=(
                McpAuthHeaderRef(
                    name="Authorization",
                    prefix="Bearer ",
                    secret_id="secret-1",
                ),
            ),
        ),
        scope="run-local",
    )

    rendered = render_mcp_config(engine, (server,), secret_resolver=lambda secret_id: "raw-token")
    root = next(iter(rendered))

    assert rendered[root]["demo"][header_key] == {"Authorization": "Bearer raw-token"}


def test_claude_materializer_writes_agent_home_and_run_local_state(tmp_path: Path) -> None:
    agent_home = tmp_path / "agent-home"
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    default_server = ResolvedMcpServer(
        definition=McpServerDefinition(
            id="default-http",
            activation="default",
            effective_engines=("claude",),
            scope="agent-home",
            transport="http",
            url="https://mcp.example/http",
            auth_headers=(
                McpAuthHeaderRef(
                    name="Authorization",
                    prefix="Bearer ",
                    secret_id="secret-header",
                ),
            ),
        ),
        scope="agent-home",
    )
    declared_server = ResolvedMcpServer(
        definition=McpServerDefinition(
            id="declared-stdio",
            activation="declared",
            effective_engines=("claude",),
            scope="run-local",
            transport="stdio",
            command="python",
            args=("-m", "demo"),
            auth_env=(McpAuthEnvRef(name="API_KEY", secret_id="secret-env"),),
        ),
        scope="run-local",
    )

    materialize_claude_mcp_resolution(
        agent_home=agent_home,
        run_dir=run_dir,
        resolution=McpResolution(servers=(default_server, declared_server)),
        secret_resolver=lambda secret_id: {
            "secret-header": "raw-token",
            "secret-env": "raw-env",
        }.get(secret_id),
    )

    payload = json.loads(active_claude_state_path(agent_home).read_text(encoding="utf-8"))
    assert payload["mcpServers"]["default-http"] == {
        "type": "http",
        "url": "https://mcp.example/http",
        "headers": {"Authorization": "Bearer raw-token"},
    }
    project_servers = payload["projects"][str(run_dir.resolve())]["mcpServers"]
    assert project_servers["declared-stdio"] == {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "demo"],
        "env": {"API_KEY": "raw-env"},
    }

    cleanup_claude_run_local_mcp(agent_home=agent_home, run_dir=run_dir)
    payload = json.loads(active_claude_state_path(agent_home).read_text(encoding="utf-8"))
    assert "default-http" in payload["mcpServers"]
    assert "mcpServers" not in payload["projects"][str(run_dir.resolve())]


def test_claude_agent_home_sync_preserves_unmanaged_entries(tmp_path: Path) -> None:
    agent_home = tmp_path / "agent-home"
    active_path = active_claude_state_path(agent_home)
    active_path.parent.mkdir(parents=True)
    active_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "user-server": {"type": "http", "url": "https://user.example/mcp"},
                    "managed-old": {"type": "http", "url": "https://old.example/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    sidecar = agent_home / ".claude" / "skill-runner-managed-mcp.json"
    sidecar.write_text(
        json.dumps({"version": 1, "agent_home": ["managed-old"], "projects": {}}),
        encoding="utf-8",
    )
    registry = {
        "managed-new": McpServerDefinition(
            id="managed-new",
            activation="default",
            effective_engines=("claude",),
            scope="agent-home",
            transport="http",
            url="https://new.example/mcp",
        )
    }

    sync_claude_agent_home_mcp(
        agent_home=agent_home,
        registry=registry,
        secret_resolver=lambda _secret_id: None,
    )

    payload = json.loads(active_path.read_text(encoding="utf-8"))
    assert "user-server" in payload["mcpServers"]
    assert "managed-old" not in payload["mcpServers"]
    assert payload["mcpServers"]["managed-new"]["url"] == "https://new.example/mcp"


def test_renderer_rejects_missing_secret() -> None:
    server = ResolvedMcpServer(
        definition=McpServerDefinition(
            id="demo",
            activation="declared",
            effective_engines=("codex",),
            scope="run-local",
            transport="stdio",
            command="python",
            auth_env=(McpAuthEnvRef(name="API_KEY", secret_id="missing"),),
        ),
        scope="run-local",
    )

    with pytest.raises(McpConfigError, match="missing secret"):
        render_mcp_config("codex", (server,), secret_resolver=lambda secret_id: None)


def test_mcp_secret_store_masks_replaces_and_deletes(tmp_path: Path) -> None:
    store = McpSecretStore(path=tmp_path / "mcp_secrets.json")

    store.upsert_secret("secret-1", "first")
    store.upsert_secret("secret-1", "second")

    assert store.get_secret("secret-1") == "second"
    raw_payload = json.loads((tmp_path / "mcp_secrets.json").read_text(encoding="utf-8"))
    assert raw_payload["secrets"]["secret-1"] == "second"
    store.delete_secrets({"secret-1"})
    assert store.get_secret("secret-1") is None


@pytest.mark.parametrize("root_key", ["mcpServers", "mcp_servers", "mcp"])
def test_direct_mcp_root_key_bypass_is_rejected(root_key: str) -> None:
    with pytest.raises(McpConfigError, match=root_key):
        validate_no_mcp_root_keys({root_key: {}}, source="test config")


def test_gemini_composer_inserts_governed_mcp_before_enforced_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = GeminiExecutionAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    (skill_dir / "assets").mkdir(parents=True)
    skill = SkillManifest(id="demo-skill", path=skill_dir)
    monkeypatch.setattr(
        "server.engines.gemini.adapter.config_composer.build_mcp_config_layer",
        lambda *, skill, engine: (
            McpResolution(servers=()),
            {"mcpServers": {"governed": {"command": "python"}}},
        ),
    )
    captured: dict[str, object] = {}

    def _capture_generate_config(schema_name: str, config_layers, output_path: Path):
        captured["schema_name"] = schema_name
        captured["layers"] = config_layers
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    with patch(
        "server.engines.gemini.adapter.config_composer.config_generator.generate_config",
        side_effect=_capture_generate_config,
    ):
        adapter._construct_config(skill, run_dir, options={})

    layers = captured["layers"]
    assert isinstance(layers, list)
    assert layers[-2]["mcpServers"]["governed"]["command"] == "python"
    assert layers[-1]["output"]["format"] == "json"


def test_gemini_composer_rejects_runtime_mcp_root_bypass(tmp_path: Path) -> None:
    adapter = GeminiExecutionAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(id="demo-skill", path=tmp_path)

    with pytest.raises(McpConfigError, match="Gemini runtime override"):
        adapter._construct_config(skill, run_dir, options={"gemini_config": {"mcpServers": {}}})


def test_codex_declared_mcp_creates_per_run_profile_and_command_uses_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_manager = MagicMock()
    config_manager.config_path = tmp_path / ".codex" / "config.toml"
    config_manager.profile_name = CodexConfigManager.PROFILE_NAME
    config_manager.generate_profile_settings.return_value = {
        "model": "gpt-5.2-codex",
        "mcp_servers": {"declared": {"command": "python"}},
    }
    adapter = CodexExecutionAdapter(config_manager=config_manager)
    run_dir = tmp_path / "run-123"
    run_dir.mkdir()
    skill = _skill_with_mcp("declared")
    declared = ResolvedMcpServer(
        definition=_stdio_server("declared", activation="declared", engines=("codex",)),
        scope="run-local",
    )
    monkeypatch.setattr(
        "server.engines.codex.adapter.config_composer.build_mcp_config_layer",
        lambda *, skill, engine: (
            McpResolution(servers=(declared,)),
            {"mcp_servers": {"declared": {"command": "python"}}},
        ),
    )
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "-p", "skill-runner"]
        if use_profile_defaults
        else [],
    )
    options: dict[str, object] = {}

    adapter._construct_config(skill, run_dir, options)
    command = adapter.build_start_command(prompt="hello", options=options)

    expected_profile = codex_run_profile_name(run_dir)
    assert options["__codex_mcp_profile_name"] == expected_profile
    assert config_manager.profile_name == expected_profile
    assert command[command.index("-p") + 1] == expected_profile
    assert config_manager.generate_profile_settings.call_args.kwargs["governed_config"] == {
        "mcp_servers": {"declared": {"command": "python"}}
    }


def test_codex_agent_home_default_mcp_uses_shared_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    config_manager = MagicMock()
    config_manager.config_path = tmp_path / ".codex" / "config.toml"
    config_manager.profile_name = CodexConfigManager.PROFILE_NAME
    config_manager.generate_profile_settings.return_value = {
        "model": "gpt-5.2-codex",
        "mcp_servers": {"default": {"command": "python"}},
    }
    adapter = CodexExecutionAdapter(config_manager=config_manager)
    run_dir = tmp_path / "run-default"
    run_dir.mkdir()
    server = ResolvedMcpServer(
        definition=_stdio_server(
            "default",
            activation="default",
            engines=("codex",),
            scope="agent-home",
        ),
        scope="agent-home",
    )
    monkeypatch.setattr(
        "server.engines.codex.adapter.config_composer.build_mcp_config_layer",
        lambda *, skill, engine: (
            McpResolution(servers=(server,)),
            {"mcp_servers": {"default": {"command": "python"}}},
        ),
    )
    options: dict[str, object] = {}

    adapter._construct_config(SkillManifest(id="demo-skill"), run_dir, options)

    assert "__codex_mcp_profile_name" not in options
    assert config_manager.profile_name == CodexConfigManager.PROFILE_NAME


def test_codex_per_run_profile_cleanup_removes_profile(tmp_path: Path) -> None:
    config_path = tmp_path / ".codex" / "config.toml"
    manager = CodexConfigManager(config_path=config_path, profile_name="skill-runner-run-demo")
    manager.update_profile({"model": "gpt-5.2-codex"})
    adapter = CodexExecutionAdapter(config_manager=manager)

    adapter.cleanup_terminal_run_resources(
        skill=SkillManifest(id="demo-skill"),
        run_dir=tmp_path / "run",
        options={"__codex_mcp_profile_name": "skill-runner-run-demo"},
    )

    doc = tomlkit.parse(config_path.read_text(encoding="utf-8"))
    assert "skill-runner-run-demo" not in doc.get("profiles", {})


def test_codex_command_builder_replaces_existing_profile_flag() -> None:
    flags = CodexCommandBuilder._replace_profile_flags(
        ["--json", "-p", "skill-runner", "--profile=other"],
        "skill-runner-run-demo",
    )

    assert flags == ["--json", "-p", "skill-runner-run-demo"]
