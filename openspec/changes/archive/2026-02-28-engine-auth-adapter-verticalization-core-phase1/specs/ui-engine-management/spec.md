## ADDED Requirements

### Requirement: 管理 UI 鉴权行为 MUST 对重构透明
系统 MUST 保持 `/ui/engines` 鉴权交互与现有 transport 接口契约兼容，不因内部目录重构改变用户可见行为。

#### Scenario: 发起与轮询鉴权
- **WHEN** 管理 UI 调用现有鉴权接口（oauth_proxy/cli_delegate）
- **THEN** 启动、轮询、输入、取消行为保持兼容
- **AND** 无需修改客户端请求路径或字段

### Requirement: 能力矩阵来源 MUST 由后端统一注入
系统 MUST 在重构后保持 `auth_ui_capabilities` 注入语义稳定，避免前端硬编码回归。

#### Scenario: 页面渲染能力矩阵
- **WHEN** UI 渲染 `/ui/engines`
- **THEN** 能力矩阵仍来自后端上下文注入
- **AND** 能力矩阵与后端 driver capability 保持一致
