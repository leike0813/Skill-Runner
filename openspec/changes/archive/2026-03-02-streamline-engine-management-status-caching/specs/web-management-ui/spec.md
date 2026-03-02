# web-management-ui Specification

## MODIFIED Requirements

### Requirement: Engine 管理页面 MUST 服务端直出首屏表格
系统 MUST 在 `/ui/engines` 首屏直接返回 engine 表格，而不是依赖首次 HTMX 拉取来补全内容。

#### Scenario: 打开 engine 管理页
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 页面首屏直接包含 engine 表格
- **AND** 不依赖 `hx-get` 首次加载表格
- **AND** 不展示“正在检测 Engine 版本与状态，请稍候...”之类延迟探测文案

### Requirement: Engine 表格 MUST 仅展示缓存化版本
系统 MUST 让 engine 管理表格只展示后台缓存的版本信息，不在页面访问时触发 CLI 版本探测。

#### Scenario: 查看 engine 表格版本列
- **WHEN** 用户查看 engine 管理表格
- **THEN** `CLI Version` 列来自持久化缓存
- **AND** 页面加载时不会触发 CLI 版本探测

### Requirement: Engine 表格 MUST 移除 auth 与 sandbox 列
系统 MUST 从 engine 管理表格中删除 auth 和 sandbox 摘要列。

#### Scenario: 查看 engine 表格列定义
- **WHEN** 用户查看 `/ui/engines`
- **THEN** 表格不包含 `Auth Ready`
- **AND** 表格不包含 `Sandbox`
