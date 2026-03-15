## ADDED Requirements

### Requirement: Engine 管理页内嵌终端在 ttyd 缺失时 MUST 前后端同时禁用
系统在 `ttyd` 不可用时 MUST 同时禁用 UI 入口和启动接口，避免用户触发不可恢复的运行时错误。

#### Scenario: ui hides TUI entry when ttyd missing
- **GIVEN** 运行环境未检测到 `ttyd` 可执行文件
- **WHEN** 用户访问 `/ui/engines` 或 `/ui/management/engines/table`
- **THEN** 页面不渲染 `Start TUI` 按钮
- **AND** 内置终端交互主面板隐藏，仅保留不可用提示

#### Scenario: tui start endpoint rejects when ttyd missing
- **GIVEN** 运行环境未检测到 `ttyd` 可执行文件
- **WHEN** 客户端调用 `POST /ui/engines/tui/session/start`
- **THEN** 后端返回 `503`
- **AND** 响应 detail 明确为依赖缺失，不再返回运行时 `500`

### Requirement: UI 首页 MUST 展示基于 ensure 缓存的引擎状态指示器
系统 MUST 在 `/ui` 首页展示引擎状态指示器，状态来源为 ensure/bootstrap 缓存快照，不执行实时 CLI 探测。

#### Scenario: ui home shows static indicator without polling
- **GIVEN** 用户访问 `/ui`
- **WHEN** 页面渲染引擎状态区块
- **THEN** 状态行按 `keys.ENGINE_KEYS` 顺序展示所有引擎
- **AND** 页面仅展示静态快照（无自动轮询刷新）

#### Scenario: ui home maps cache snapshot to led levels
- **GIVEN** 缓存快照包含 `present` 与 `version` 字段
- **WHEN** 页面计算状态灯颜色
- **THEN** `present=true` 且 `version` 非空显示绿灯
- **AND** `present=true` 且 `version` 为空显示黄灯
- **AND** `present=false` 显示红灯
