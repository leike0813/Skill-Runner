## Why

当前执行链路在“主服务 API 执行”和“外挂 Harness 执行”之间存在命令构建与引擎解析的分叉，导致参数来源、行为与验证结果不一致。随着引擎与交互协议继续演进，需要把引擎相关能力统一收口到 Adapter，并让主服务与 Harness 复用同一核心执行路径。

## What Changes

- 将引擎特定职责（命令构建、流解析、会话句柄提取与恢复命令）统一定义为 Adapter 通用接口，并由各引擎 Adapter 实现。
- 将运行中消息流协议重构中与引擎相关的解析逻辑从通用服务迁移到 Adapter；通用层仅保留 RASP/FCMP 组装与去重。
- 新增命令参数 Profile 机制，仅用于后端 API 链路的默认参数注入（配置文件驱动）。
- 明确 Harness 执行参数策略：不使用 Profile 默认参数，完全以用户透传参数驱动命令构建。
- 新增临时 `opencode` Adapter（占位实现）：先承接可迁移解析逻辑，执行能力未实现部分显式返回能力不足。
- 调整 Harness 与后端执行编排，使其调用同一 Adapter 接口完成命令构建与流解析，消除双轨实现。

## Capabilities

### New Capabilities
- `engine-adapter-runtime-contract`: 定义跨引擎统一 Adapter 运行时接口（start/resume 命令构建、runtime 流解析、会话恢复元信息）。
- `engine-command-profile-defaults`: 定义 API 链路的引擎命令默认参数 Profile（配置文件化）与覆盖规则。
- `harness-shared-adapter-execution`: 定义 Harness 复用 Adapter 核心链路且不注入 Profile 默认参数的执行规则。

### Modified Capabilities
- `interactive-run-observability`: 运行中事件的引擎解析来源由通用解析函数调整为 Adapter 提供的解析结果，通用层仅负责协议组装。

## Impact

- Affected code:
  - `server/adapters/*`, `server/services/job_orchestrator.py`, `server/services/runtime_event_protocol.py`
  - 新增命令 profile 配置与加载服务
  - `agent_harness/*`（切换为共享 Adapter 执行链路）
- Affected APIs:
  - HTTP API 路径不变；执行行为来源统一
  - Harness CLI 参数语义不变，但底层命令构建来源调整
- Affected systems:
  - 引擎执行与解析一致性提升，回归与审计对照更稳定
  - 未来新增引擎只需补 Adapter 实现，降低耦合成本
