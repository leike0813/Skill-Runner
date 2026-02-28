# Adapter Component Guide

## 1. 背景

phase2 后，执行适配器按引擎垂直化到：
- `server/engines/<engine>/adapter/*`

同时通过组件契约统一抽象，避免继续扩张单体 adapter。
phase1 后旧单体 `server/engines/*/adapter/adapter.py` 与 `server/adapters/base.py` 已移除。

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
`EngineAdapterRegistry` 会直接实例化该类，不再经过 `entry.py`。

`PromptBuilder / SessionHandleCodec / WorkspaceProvisioner` 三类组件统一由
`server/runtime/adapter/common/*` 的 `Profiled*` 实现承接，并通过每个引擎的
`adapter_profile.json` 注入差异。

`adapter_profile.json` 现已扩展为引擎执行资产单源，除 prompt/session/workspace 外还包含：
1. `config_assets`
   - `bootstrap_path/default_path/enforced_path/settings_schema_path/skill_defaults_path`
2. `model_catalog`
   - `mode/manifest_path/models_root/seed_path`

这些路径由 profile loader 在初始化阶段 fail-fast 校验，避免运行时隐式回退。

## 4. I/O 约定

1. 输入上下文：`AdapterExecutionContext`
   - `skill/run_dir/input_data/options`
2. 输出结果：`AdapterExecutionArtifacts`
   - 原始输出、结构化输出、session handle、错误信息

## 5. 新引擎实现最小清单

1. 新建 `server/engines/<new>/adapter/` 目录。
2. 实现 `config_composer.py`、`command_builder.py`、`stream_parser.py`、`execution_adapter.py`。
3. 提供 `adapter_profile.json`（至少包含 prompt/session/workspace/config_assets/model_catalog）。
4. 在 `server/services/engine_adapter_registry.py` 注册 execution adapter class。
4. 补单测：
   - 组件契约测试
   - 命令构建测试
   - 解析测试
   - 句柄恢复测试

## 6. 常见问题

1. 配置路径异常：
   - 优先检查 `adapter_profile.json` 的 `config_assets` 与 `model_catalog` 路径。
2. resume 失败：
   - 检查 `SessionHandleCodec` 是否与 parser 产物一致。
3. 结果校验误报：
   - 优先检查 `StreamParser` 的 done 标记提取范围是否仅限 agent 输出语义。
