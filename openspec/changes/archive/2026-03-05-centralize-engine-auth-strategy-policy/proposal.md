## Why

当前 Engine 鉴权能力矩阵分散在 UI、会话编排与 driver registry 的多处硬编码中，扩展新 provider 或调整鉴权方式时容易产生行为漂移。需要把能力定义收敛到单一策略文件，确保 UI 展示、会话鉴权与启动校验使用同一真相源。

## What Changes

- 新增 `engine_auth_strategy.yaml` 与 schema，集中描述 engine/provider 在 `oauth_proxy` 与 `cli_delegate` 下支持的鉴权方式。
- 新增策略加载服务，统一提供 UI 能力查询、会话内可用方式查询、启动组合校验查询。
- `engine_auth_bootstrap` 改为通过策略服务动态注册 `AuthDriverRegistry`，移除硬编码组合。
- `ui_engines` 改为注入策略服务提供的 `auth_ui_capabilities`，移除 router 内部硬编码矩阵逻辑。
- `run_auth_orchestration_service` 改为通过策略服务计算 `available_methods`，会话内固定走 `oauth_proxy` 轨道。
- OpenCode provider 采用策略文件显式列举，未配置 provider 视为不支持该能力组合。

## Capabilities

### New Capabilities

- `engine-auth-strategy-policy`: 统一定义并校验 engine/provider 鉴权能力矩阵，供 UI、编排与启动校验共享。

### Modified Capabilities

- `ui-engine-management`: 鉴权菜单能力来源改为后端策略文件，不允许硬编码回退。
- `in-conversation-auth-method-selection`: waiting_auth 的 `available_methods` 必须来源于策略文件。
- `in-conversation-auth-flow`: waiting_auth challenge 编排必须受策略文件约束。
- `engine-auth-observability`: 启动组合校验能力与 UI 可见能力必须同源。

## Impact

- 受影响代码：
  - `server/services/engine_management/engine_auth_bootstrap.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/routers/ui.py`
  - `server/assets/templates/ui/engines.html`
- 新增代码与配置：
  - `server/services/engine_management/engine_auth_strategy_service.py`
  - `server/assets/configs/engine_auth_strategy.yaml`
  - `server/assets/schemas/engine_auth/engine_auth_strategy.schema.json`
- 外部 API 路径与 payload 结构保持不变。
