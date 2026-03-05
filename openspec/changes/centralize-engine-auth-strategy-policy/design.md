## Context

当前鉴权能力在三处重复维护：

1. `engine_auth_bootstrap` 的 driver registry 注册矩阵。
2. `ui.py::_build_auth_ui_capabilities` 的菜单矩阵。
3. `run_auth_orchestration_service::_available_methods_for` 的会话内方式矩阵。

这些定义一旦偏离，会导致「UI 可见但无法启动」或「会话编排与管理 UI 不一致」。

## Goals

- 使用单一策略文件定义能力矩阵，并以 schema 校验。
- 让 UI、会话编排、driver registry 全部通过同一服务读取策略。
- 保持会话内交互形态不变：仅选择 `auth_method`，不选择 transport。

## Strategy Model

新增配置文件：`server/assets/configs/engine_auth_strategy.yaml`

新增 schema：`server/assets/schemas/engine_auth/engine_auth_strategy.schema.json`

核心结构：

- `engines.<engine>.transports.<transport>.methods`
- `engines.<engine>.transports.<transport>.driver.start_method|execution_mode`
- `engines.<engine>.in_conversation.transport`
- `engines.<engine>.in_conversation.methods`（会话内展示方法集合）
- `engines.opencode.providers.<provider_id>...`（provider 显式列举）

说明：

- transport methods 使用 runtime method 语义：`callback|auth_code_or_url|api_key`。
- in-conversation methods 使用会话语义：`callback|device_auth|authorization_code|api_key`。
- OpenCode provider 必须显式声明；未声明则视为不支持。

## Components

### 1) EngineAuthStrategyService

文件：`server/services/engine_management/engine_auth_strategy_service.py`

职责：

- 读取 YAML + JSON schema 并校验。
- 暴露统一查询：
  - `list_ui_capabilities()`
  - `iter_driver_entries()`
  - `methods_for_conversation(engine, provider_id)`
  - `resolve_conversation_transport(engine, provider_id)`
  - `supports_start(transport, engine, auth_method, provider_id)`

约束：

- 初始化失败直接抛出 `RuntimeError`，避免 silent fallback。
- 统一小写化输出，保证调用端不做重复 normalize。

### 2) Driver Registry Bootstrap

文件：`server/services/engine_management/engine_auth_bootstrap.py`

改造：

- 删除硬编码 `_register_auth_driver(...)` 批量调用。
- 改为遍历 `engine_auth_strategy_service.iter_driver_entries()` 动态注册。
- 保持现有 `start_method` 与 `execution_mode` 语义，不改 runtime handler 行为。

### 3) Management UI Capability Injection

文件：`server/routers/ui.py`

改造：

- 删除 `_build_auth_ui_capabilities(...)` 硬编码逻辑。
- `ui_engines` 直接注入 `engine_auth_strategy_service.list_ui_capabilities()`。
- `opencode_auth_providers` 继续来自 provider registry（展示层元信息），但可用方法由策略文件决定。

### 4) In-conversation Auth Orchestration

文件：`server/services/orchestration/run_auth_orchestration_service.py`

改造：

- `_available_methods_for` 改为调用策略服务。
- 固定读取 `resolve_conversation_transport(...)=oauth_proxy` 对应的会话方法集合。
- `PendingAuthMethodSelection.available_methods` 与 `ask_user.options` 由策略服务结果构造。

## Compatibility

- 不新增 transport 选择字段，不修改 `InteractionReplyRequest`。
- 不修改外部 API 路径或鉴权提交协议。
- 仅统一能力来源，保持当前功能行为矩阵不变。

## Risks

- 风险：策略文件与 runtime handler 真实能力不匹配，导致运行时 422/409。
  - 缓解：单测覆盖 driver supports 与 UI capabilities 一致性。
- 风险：OpenCode provider 遗漏导致能力消失。
  - 缓解：在测试中断言策略 provider 集合至少覆盖 registry provider 集合。

## Validation Plan

- 单测：
  - 策略文件 schema 校验、查询输出、异常路径。
  - driver registry 注册结果来源验证。
  - UI capabilities 注入来源验证。
  - 会话编排 `available_methods` 来源验证。
- 回归：
  - `oauth_proxy` 与 `cli_delegate` 在管理 UI 中菜单仍可用。
  - waiting_auth 在各 engine/provider 下选择路径与 challenge 路径不变。
