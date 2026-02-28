## Design Summary

本 change 采用“runtime 公共内核 + engine 差异组件”结构：

1. runtime 负责统一执行生命周期与共性工具。
2. engine 目录只保留差异行为（配置、命令、解析细节）。
3. 删除旧单体 adapter 与旧 base 路径，消除双轨。
4. `PromptBuilder / SessionCodec / WorkspaceProvisioner` 三类组件改为 profile 注入，不再保留引擎侧实现文件。
5. 引擎 adapter 不再使用 `entry.py` 工厂入口，registry 直接实例化 `execution_adapter.py` 中的类。

## Architecture

### Runtime Adapter Core

- `server/runtime/adapter/base_execution_adapter.py`
  - 统一 run 生命周期（配置、workspace、prompt、执行、解析、结果落盘）。
  - 统一子进程/超时/取消/错误归类。
- `server/runtime/adapter/types.py`
  - 统一 `EngineRunResult`、`ProcessExecutionResult`、runtime stream parse typed structures。

### Runtime Common Components

- `server/runtime/adapter/common/prompt_builder_common.py`
- `server/runtime/adapter/common/session_codec_common.py`
- `server/runtime/adapter/common/workspace_provisioner_common.py`
- `server/runtime/adapter/common/profile_loader.py`

用于承接跨引擎高重复逻辑，禁止放入 engine-specific 规则。三类组件由 `adapter_profile.json` 驱动：

1. Prompt 模板选择与上下文拼装（含 input/parameter、prompt source）
2. Session handle 提取策略（first_json/json_lines/recursive/regex）
3. Workspace 目录与 skills 安装路径策略

Profile 启动即校验（fail-fast），任何引擎 profile 非法都会阻断服务初始化。

### Engine Components

每个引擎保留：

1. `config_composer.py`
2. `command_builder.py`
3. `stream_parser.py`
4. `execution_adapter.py`（轻量执行上下文/依赖注入 + profile 接线）
5. `adapter_profile.json`

## Constraints

1. 禁止保留 `build_adapter()`。
2. 禁止保留 `server/adapters/base.py`。
3. `runtime/common` 只放引擎无关逻辑。
4. `server/engines/*/adapter/entry.py` 禁止存在。
5. `server/engines/*/adapter/prompt_builder.py`、`session_codec.py`、`workspace_provisioner.py` 禁止存在。
6. `engine_adapter_registry` 必须直接实例化 execution adapter，不允许依赖包级工厂函数。
7. profile 校验必须 fail-fast（初始化阶段失败即阻断服务启动）。
8. 对外 API、路由语义保持不变。

## Compatibility

1. `job_orchestrator` 仍通过 `adapter.run(...)` 执行。
2. `runtime_event_protocol` 仍通过 `adapter.parse_runtime_stream(...)` 解析。
3. 兼容现有 session handle 提取与 resume 命令构建行为。
