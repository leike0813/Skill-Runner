## MODIFIED Requirements

### Requirement: UI auth flow remains stable across internal runtime refactor
`/ui/engines` 的鉴权交互 MUST 在 phase2 后保持行为兼容，不因内部模块重组改变用户操作路径。

#### Scenario: UI starts auth session
- **WHEN** 用户在管理页发起鉴权
- **THEN** 仍通过既有 `/ui/engines/auth/*` 路由完成 start/status/input/cancel
- **AND** 返回字段与状态语义兼容现有页面逻辑

### Requirement: UI capability matrix remains backend-injected
前端鉴权能力矩阵 MUST 继续由后端上下文注入，避免在页面脚本中硬编码引擎能力。

#### Scenario: Rendering auth capability menu
- **WHEN** 页面渲染引擎鉴权菜单
- **THEN** 能力矩阵来自后端注入数据
- **AND** 与 runtime driver 注册矩阵一致
