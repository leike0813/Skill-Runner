## MODIFIED Requirements

### Requirement: Engine 管理页面 MUST 服务端直出首屏表格
系统 MUST 保持模型管理页服务端渲染，并统一模型展示与输入语义。

#### Scenario: 模型管理页统一为单一 model 展示语义
- **WHEN** 用户访问 `/ui/engines/{engine}/models`
- **THEN** 模型列表不再显示 `display_name` 列
- **AND** `opencode` 继续在 `model` 列显示当前 `model` 值
- **AND** 其他引擎在 `model` 列显示原 `display_name` 内容

#### Scenario: 非 opencode 模型快照表单统一为 model 输入
- **WHEN** 用户在非 `opencode` 模型管理页新增快照行
- **THEN** 表单不再单独提供 `display_name` 输入
- **AND** 页面以单一 `model` 输入承载原显示名语义

#### Scenario: opencode 手动刷新通过局部更新返回
- **WHEN** 用户在 `opencode` 模型管理页点击手动刷新
- **THEN** 页面 MUST 通过 HTMX 局部替换更新模型管理 panel
- **AND** 不得退回整页重定向刷新
