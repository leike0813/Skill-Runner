## ADDED Requirements

### Requirement: 管理 UI MUST 提供 codex 与 opencode/openai 的 2x2 测试入口
系统 MUST 在 `/ui/engines` 为测试阶段提供显式 2x2 按钮矩阵。

#### Scenario: codex 2x2 按钮可用
- **WHEN** 用户查看 Engine 管理页
- **THEN** 页面展示 codex 的 4 个入口：
- `oauth_proxy + browser-oauth`
- `oauth_proxy + device-auth`
- `cli_delegate + browser-oauth`
- `cli_delegate + device-auth`

#### Scenario: opencode/openai 2x2 按钮可用
- **WHEN** 用户查看 Engine 管理页
- **THEN** 页面展示 opencode(openai) 的 4 个入口：
- `oauth_proxy + browser-oauth`
- `oauth_proxy + device-auth`
- `cli_delegate + browser-oauth`
- `cli_delegate + device-auth`

### Requirement: UI start 请求 MUST 透传 auth_method
系统 MUST 在鉴权启动请求中携带 `auth_method`，而非仅依赖历史 `method`。

#### Scenario: 点击矩阵按钮
- **WHEN** 用户点击任一矩阵入口
- **THEN** UI 请求体包含 `transport + auth_method`
- **AND** opencode/openai 请求体携带 `provider_id=openai`

### Requirement: 输入区展示 MUST 与 auth_method 匹配
系统 MUST 根据 `engine + transport + auth_method + input_kind` 控制输入区和提示文案。

#### Scenario: browser OAuth
- **WHEN** 会话为 browser OAuth 且需要手工回填
- **THEN** 显示 redirect URL/code 粘贴提示与提交入口

#### Scenario: device-auth
- **WHEN** 会话为 device-auth 且不需要用户向后端回填
- **THEN** 不显示输入框
- **AND** 保留 `verification_url + user_code` 展示

### Requirement: 提交后隐藏行为 MUST 继续生效
系统 MUST 保持“输入提交后隐藏输入区与鉴权链接”的既有行为，避免重复误操作。

#### Scenario: 提交成功接受
- **WHEN** `/input` 返回 `accepted=true`
- **THEN** 输入区与链接区域隐藏
- **AND** 状态切换为等待结果
