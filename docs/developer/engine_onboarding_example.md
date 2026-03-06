# Engine Onboarding Guide

This document walks through adding a new engine `demo` to Skill Runner, step by step.

## Prerequisites

- The engine has a CLI tool installable via npm
- The engine reads a config file and writes output to stdout/stderr
- Auth is handled via OAuth, API key, or similar mechanism

## Step 1: Create Engine Package

```text
server/engines/demo/
  __init__.py
  adapter/
    __init__.py
    adapter_profile.json        ← engine 配置单源
    execution_adapter.py        ← 执行入口
    config_composer.py          ← 配置合成
    command_builder.py          ← 命令构建
    stream_parser.py            ← 输出解析
  auth/
    __init__.py
    detection.py                ← auth 检测器
    runtime_handler.py          ← auth 运行时处理
    protocol/                   ← auth 协议细节
    callbacks/                  ← OAuth 回调处理
  config/
    auth_strategy.yaml          ← 认证支持矩阵
    command_profile.json        ← TUI shell 命令配置
    bootstrap.json              ← 引导配置默认值
    default.json                ← 默认运行配置
    enforced.json               ← 强制运行配置
  models/
    manifest.json               ← 模型目录清单
    models_1.0.0.json           ← 至少一个模型快照
  schemas/                      ← (可选) settings 校验 schema
```

## Step 2: Create `adapter_profile.json`

这是引擎的**核心配置文件**，框架通过它驱动 CLI 管理、模型目录、缓存键构建等所有行为。

```jsonc
{
  "engine": "demo",
  "prompt_builder": {
    "engine_key": "demo",
    "default_template_path": "../../../assets/templates/demo_default.j2",
    "fallback_inline": "{{ input_prompt }}",
    "merge_input_if_no_parameter_schema": false,
    "params_json_source": "none",
    "main_prompt_source": "parameter.prompt",
    "main_prompt_default_template": "Execute skill {skill_id}",
    "include_input_file_name": false,
    "include_skill_dir": false
  },
  "session_codec": {
    "strategy": "json_lines_extract",
    "error_message": "SESSION_RESUME_FAILED: missing demo session-id",
    "error_prefix": null,
    "required_type": null,
    "id_field": "session_id",
    "recursive_key": null,
    "fallback_text_finder": null,
    "json_lines_finder": { "key": "session_id" },
    "regex_pattern": null
  },
  "attempt_workspace": {
    "workspace_subdir": ".demo",
    "skills_subdir": "skills",
    "use_config_parent_as_workspace": false,
    "unknown_fallback": false
  },
  "config_assets": {
    "bootstrap_path": "../config/bootstrap.json",
    "default_path": "../config/default.json",
    "enforced_path": "../config/enforced.json",
    "settings_schema_path": null,
    "skill_defaults_path": null
  },
  "model_catalog": {
    "mode": "manifest",
    "manifest_path": "../models/manifest.json",
    "models_root": "../models",
    "seed_path": null
  },
  "cli_management": {
    "package": "@demo-ai/demo-cli",
    "binary_candidates": ["demo", "demo.cmd", "demo.exe"],
    "credential_imports": [
      { "source": "demo_credentials.json", "target_relpath": ".demo/credentials.json" }
    ],
    "credential_policy": {
      "mode": "all_of_sources",
      "sources": ["demo_credentials.json"],
      "settings_validator": null
    },
    "resume_probe": {
      "help_hints": ["--resume"],
      "dynamic_args": ["--resume", "probe", "--help"]
    },
    "layout": {
      "extra_dirs": [".demo"],
      "bootstrap_target_relpath": ".demo/config.json",
      "bootstrap_format": "json",
      "normalize_strategy": null
    }
  }
}
```

详细字段说明参见 [adapter_profile_reference.md](adapter_profile_reference.md)。

## Step 3: Implement Adapter Components

### `execution_adapter.py`

继承 `EngineExecutionAdapter`，持有并组装其他组件：

```python
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter

class DemoExecutionAdapter(EngineExecutionAdapter):
    @property
    def engine_name(self) -> str:
        return "demo"

    # 实现 config_composer / command_builder / stream_parser
    # 或委托给 Profiled* 通用实现
```

### `config_composer.py` / `command_builder.py` / `stream_parser.py`

按引擎 CLI 的实际行为实现。可参考现有引擎（如 `server/engines/iflow/adapter/`）。

## Step 4: Implement Auth

### `auth/detection.py`

实现 `AuthDetector` 协议：

```python
from server.runtime.auth_detection.contracts import AuthDetector

class DemoAuthDetector:
    def detect(self, ...) -> ...:
        # 检测用户是否已认证
        ...
```

### `auth/runtime_handler.py`

实现 9 个 handler contract 方法（详见 [auth_runtime_driver_guide.md](auth_runtime_driver_guide.md#3-engine-runtime-handler-contract)）。

### `config/auth_strategy.yaml`

定义引擎支持的认证矩阵：

```yaml
oauth_proxy:
  oauth:
    demo_provider:
      start_method: redirect
      execution_mode: interactive
cli_delegate:
  api_key:
    demo_provider:
      start_method: direct
      execution_mode: auto
```

## Step 5: Create Model Catalog

### `models/manifest.json`

```json
{
  "engine": "demo",
  "snapshots": [
    { "version": "1.0.0", "file": "models_1.0.0.json" }
  ]
}
```

### `models/models_1.0.0.json`

```json
{
  "engine": "demo",
  "version": "1.0.0",
  "models": [
    {
      "id": "demo-standard",
      "display_name": "Demo Standard",
      "deprecated": false,
      "notes": null
    }
  ]
}
```

如果引擎的模型是运行时动态发现的而非静态快照，将 `adapter_profile.json` 中 `model_catalog.mode` 设为 `"runtime_probe"` 并实现 `RuntimeProbeCatalogHandler`（参见 `engine_model_catalog_lifecycle.py`）。

## Step 6: Framework Registration

在以下文件中各添加一行注册：

### 6.1 `server/config_registry/keys.py`

```python
ENGINE_KEYS = ("codex", "demo", "gemini", "iflow", "opencode")
```

### 6.2 `server/services/engine_management/engine_adapter_registry.py`

```python
from server.engines.demo.adapter.execution_adapter import DemoExecutionAdapter

# 在 validate_adapter_profiles() 中添加路径
# 在 self._adapters 中添加
"demo": DemoExecutionAdapter(),
```

### 6.3 `server/services/engine_management/engine_auth_bootstrap.py`

```python
from server.engines.demo.auth.runtime_handler import DemoAuthRuntimeHandler

# 在 build_engine_auth_bootstrap() 的 handlers 字典中添加
"demo": DemoAuthRuntimeHandler(manager),
```

### 6.4 `server/runtime/auth_detection/detector_registry.py`

```python
from server.engines.demo.auth.detection import DemoAuthDetector

# 在 create_default_auth_detector_registry() 中添加
"demo": DemoAuthDetector(),
```

### 6.5 `server/services/ui/engine_shell_capability_provider.py`（可选）

如果 `demo` 的 shell 行为与默认 fallback 不同，在 `_build_capabilities()` 中注册自定义 capability。否则框架会使用通用 fallback 自动适配。

## Step 7: Tests

### 必须通过的测试

1. `test_runtime_auth_no_engine_coupling.py` — runtime 层无引擎硬编码守卫
2. Auth driver matrix registration — demo 引擎的认证组合能正确解析
3. Auth flow round-trip — start → status → input → callback → cancel

### 建议补充的测试

1. `command_builder` — start/resume 命令参数正确
2. `stream_parser` — stdout/stderr 解析为正确的结果语义
3. `session_handle_codec` — 句柄提取与恢复
4. `config_composer` — default + skill + enforced 合成优先级

## 不需要修改的文件

以下核心框架文件通过 `adapter_profile.json` 和注册表**自动适配**新引擎：

- `server/services/engine_management/agent_cli_manager.py` — 从 profile 读取包名/二进制名/凭据/目录/resume 参数
- `server/services/engine_management/model_registry.py` — 从 profile 读取 model catalog 模式和路径
- `server/services/platform/cache_key_builder.py` — 从 profile 读取 skill_defaults_path
- `server/services/platform/data_reset_service.py` — 从 lifecycle 获取 cache 路径
- `server/routers/ui.py` — 通过 registry 和 lifecycle 接口适配
- `server/main.py` — 通过 lifecycle 接口适配
