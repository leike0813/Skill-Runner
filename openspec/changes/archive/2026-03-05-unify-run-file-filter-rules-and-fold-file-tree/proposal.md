## Why

当前 debug bundle 和 run 文件树缺少统一过滤规则，`opencode` 运行时落盘的 `node_modules` 会导致打包体积和文件树噪声急剧上升。需要把过滤策略收敛为集中配置，并同步统一管理端与 e2e 客户端的文件树交互行为。

## What Changes

- 新增 run 文件过滤规则中心，拆分为两个独立规则文件：
  - 非 debug bundle 白名单规则文件
  - debug bundle 黑名单规则文件
- 非 debug bundle 改为严格按白名单打包（从现有逻辑抽取：`result/result.json`、`artifacts/**`）。
- debug bundle 改为按黑名单排除；默认忽略任意层级 `node_modules` 目录及其全部内容。
- run explorer（后端文件树与文件预览）复用 debug 黑名单规则，隐藏被忽略目录及其子内容。
- 管理 UI 与 e2e 客户端文件树统一支持目录折叠，且默认全部目录为折叠状态。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `job-orchestrator-modularization`: run bundle 候选文件选择改为规则文件驱动，区分非 debug 白名单与 debug 黑名单。
- `run-observability-ui`: run 文件树与文件预览必须应用统一过滤规则，并提供默认折叠目录树交互。
- `builtin-e2e-example-client`: 结果页/观察页文件树与预览必须遵循同一过滤规则并默认折叠目录。

## Impact

- 受影响代码：
  - `server/services/orchestration/run_bundle_service.py`
  - `server/runtime/observability/run_observability.py`
  - `server/services/skill/skill_browser.py`（如需新增 run 专用树构建入口）
  - `server/assets/templates/ui/run_detail.html`
  - `e2e_client/templates/run_observe.html`
- 新增配置文件：
  - `server/assets/configs/run_bundle_allowlist_non_debug.ignore`
  - `server/assets/configs/run_bundle_denylist_debug.ignore`
- 受影响测试：
  - bundle manifest、run observability、管理 UI、e2e client 文件树交互相关单测。
