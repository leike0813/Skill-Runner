## 1. OpenSpec Artifacts

- [x] 1.1 完成 proposal/design/tasks 与 delta specs，明确“策略文件唯一来源”合同。

## 2. Strategy File and Schema

- [x] 2.1 新增 `server/assets/configs/engine_auth_strategy.yaml`，覆盖 codex/gemini/iflow/opencode 全矩阵。
- [x] 2.2 新增 `server/assets/schemas/engine_auth/engine_auth_strategy.schema.json` 并定义约束。
- [x] 2.3 新增 `engine_auth_strategy_service`，实现加载、校验与统一查询 API。

## 3. Integrations

- [x] 3.1 改造 `engine_auth_bootstrap`，由策略服务驱动 `AuthDriverRegistry` 注册。
- [x] 3.2 改造 `ui_engines` 注入逻辑，移除 `_build_auth_ui_capabilities` 硬编码矩阵。
- [x] 3.3 改造 `run_auth_orchestration_service`，waiting_auth 方法集合改由策略服务提供（固定 oauth_proxy）。

## 4. Tests

- [x] 4.1 新增策略服务与 schema 单测。
- [x] 4.2 更新 driver matrix 与 UI routes 单测，验证能力来源同一策略文件。
- [x] 4.3 更新 run auth orchestration 单测，验证 available_methods 与 challenge 路径由策略驱动。

## 5. Validation

- [x] 5.1 运行 runtime/auth 关键测试集并通过。
- [x] 5.2 运行 mypy（变更文件）并通过。
- [x] 5.3 `openspec validate --change centralize-engine-auth-strategy-policy` 通过。
