# Adapter Component Guide

## 1. 背景

执行适配器按引擎垂直化到：
- `server/engines/<engine>/adapter/*`

通过组件契约统一抽象，避免继续扩张单体 adapter。

## 2. 六个标准组件

1. `ConfigComposer`
   - 负责 engine 配置合成（default + skill + runtime options + enforced）
2. `WorkspaceProvisioner`
   - 负责 run folder 内目录、技能安装、配置落盘
3. `PromptBuilder`
   - 负责 prompt 模板渲染与输入拼装
4. `CommandBuilder`
   - 负责 start/resume 命令构建与参数映射
5. `StreamParser`
   - 负责 stdout/stderr 解析到统一结果语义
6. `SessionHandleCodec`
   - 负责 interactive 会话句柄提取与恢复

## 3. 装配方式

每个引擎的入口为 `execution_adapter.py` 中的类（例如 `CodexExecutionAdapter`）。
`EngineAdapterRegistry` 会直接实例化该类。

`PromptBuilder / SessionHandleCodec / WorkspaceProvisioner` 三类组件统一由
`server/runtime/adapter/common/*` 的 `Profiled*` 实现承接，并通过每个引擎的
`adapter_profile.json` 注入差异。

`adapter_profile.json` 是引擎配置的**单一数据源**。当前实现中的主要顶层节包括：

| 节 | 用途 |
|---|---|
| `provider_contract` | 单 provider / 多 provider 合同与 canonical provider 约束 |
| `prompt_builder` | skill 调用首行模板，以及默认 body 模板前后的可选 extra block |
| `session_codec` | 会话句柄提取策略（regex/json/text） |
| `attempt_workspace` | run folder 目录布局 |
| `config_assets` | bootstrap/default/enforced/settings_schema/skill_defaults 路径 |
| `model_catalog` | 模型目录模式（`manifest` 或 `runtime_probe`）和路径 |
| `command_defaults` | start / resume / ui_shell 的默认 CLI 参数 |
| `structured_output` | 结构化输出 CLI 注入、compat schema、payload canonicalization 策略 |
| `ui_shell` | UI shell 命令、sandbox 提示与运行时 override 策略 |
| `cli_management` | CLI 管理全配置（见下） |
| `parser_auth_patterns` | engine-specific auth 高置信检测规则 |

`cli_management` 子节管理引擎 CLI 的安装、凭据、目录布局和恢复探测：

| 字段 | 用途 |
|---|---|
| `package` | npm 包名（如 `@google/gemini-cli`） |
| `binary_candidates` | CLI 可执行文件候选名 |
| `credential_imports` | 凭据文件导入映射（source → target_relpath） |
| `credential_policy` | 凭据就绪判定策略（`all_of_sources` / `any_of_sources`） |
| `resume_probe` | 恢复能力探测参数（help_hints + dynamic_args） |
| `layout` | 目录创建（extra_dirs）、bootstrap 写入路径和格式 |

详见 [adapter_profile_reference.md](adapter_profile_reference.md)。

## 4. I/O 约定

1. 输入上下文：`AdapterExecutionContext`
   - `skill/run_dir/input_data/options`
2. 输出结果：`AdapterExecutionArtifacts`
   - 原始输出、结构化输出、session handle、错误信息

## 5. 新引擎实现最小清单

### 5.1 引擎包内文件

1. 新建 `server/engines/<new>/adapter/` 并实现：
   - `adapter_profile.json`（必须，符合当前 schema）
   - `execution_adapter.py`（必须）
   - `config_composer.py`（必须）
   - `command_builder.py`（必须）
   - `stream_parser.py`（必须）
2. 新建 `server/engines/<new>/config/` 并创建：
   - `auth_strategy.yaml`（认证支持矩阵）
   - profile 所引用的 `bootstrap/default/enforced` 配置资产
3. 新建 `server/engines/<new>/models/` 并提供：
   - `manifest.json` + 至少一个 `models_*.json` snapshot

### 5.2 框架注册点

以下是添加新引擎时需要修改的框架文件（均为**声明式注册**，每处仅需加一行）：

| # | 文件 | 修改内容 |
|---|---|---|
| 1 | `server/config_registry/keys.py` | 在 `ENGINE_KEYS` 元组中追加引擎名 |
| 2 | `server/services/engine_management/engine_adapter_registry.py` | import 并注册 execution adapter |
| 3 | `server/services/engine_management/engine_auth_bootstrap.py` | import 并注册 auth runtime handler |
| 4 | `server/runtime/auth_detection/detector_registry.py` | import 并注册 auth detector |
| 5 | `server/services/ui/engine_shell_capability_provider.py` | （可选）注册 shell capability，有通用 fallback |

注意：**不需要修改** `agent_cli_manager.py`、`cache_key_builder.py`、`model_registry.py`、`routers/ui.py` 或 `main.py`——这些模块通过 `adapter_profile.json` 和注册表自动适配新引擎。

### 5.3 单测

- 组件契约测试
- 命令构建测试
- 解析测试
- 句柄恢复测试
- `test_runtime_auth_no_engine_coupling.py` 需保持通过

## 6. 常见问题

1. 配置路径异常：
   - 优先检查 `adapter_profile.json` 中路径是否相对于 profile 文件自身位置。
   - profile_loader 在加载时做 fail-fast 校验，缺失文件会立即报错。
2. resume 失败：
   - 检查 `adapter_profile.json` 的 `session_codec` 和 `cli_management.resume_probe` 配置。
3. 结果校验误报：
   - 优先检查 `StreamParser` 的 done 标记提取范围是否仅限 agent 输出语义。
4. CLI 未检测到：
   - 检查 `cli_management.binary_candidates` 是否包含当前平台的可执行文件名。
