## Why

`/ui/engines` 的鉴权入口目前是“按 transport + auth_method 展开成大量按钮”，存在三类问题：
1. 同一页面按钮数量过多，用户很难先做“链路选择”，再做“方式选择”。
2. 能力矩阵逻辑分散在模板硬编码中，变更后易与后端能力发生漂移。
3. 鉴权状态窗口与启动按钮混杂，运行中禁用逻辑难以统一维护。

本 change 仅收敛管理 UI 的交互编排，不改变后端鉴权状态机或 API 契约。

## What Changes

1. 将 `oauth_proxy / cli_delegate` 收敛为全局“鉴权后台”下拉（默认 `oauth_proxy`，鉴权进行中禁用）。
2. 引擎表格 Actions 区每个引擎保留一个“连接”入口按钮，点击后按当前后台展示鉴权方式菜单。
3. OpenCode 鉴权入口改为“provider -> 鉴权方式”两级子菜单。
4. 主鉴权状态窗口仅保留状态展示与输入区域，启动按钮移除，仅保留“取消”按钮。
5. 在 `auth_code_or_url` 且显示 `user_code` 时，为 `codex` 与 `opencode+openai` 增加复制按钮（两条 transport 均支持）。
6. UI 渲染能力矩阵改为由后端注入 `auth_ui_capabilities`，避免前端硬编码漂移。

## Scope

### In Scope

1. `server/routers/ui.py` 模板上下文增强（`auth_ui_capabilities`）。
2. `/ui/engines` 页面模板与前端脚本重构（不改接口路径）。
3. 引擎表格局部模板按钮收敛。
4. 相关 UI 单测断言更新与文档同步。

### Out of Scope

1. 不新增 transport 类型。
2. 不修改 `/v1` 鉴权接口契约与鉴权状态机。
3. 不调整后端引擎能力矩阵本质，仅做 UI 映射。

## Success Criteria

1. 页面存在全局鉴权后台下拉，且鉴权会话进行中被禁用。
2. 引擎表格每行仅一个鉴权入口按钮；OpenCode 可完成 provider->方式选择。
3. 主鉴权窗口不再包含启动按钮，仅保留取消按钮、状态信息和必要输入区。
4. `codex` 与 `opencode+openai` 的 `auth_code_or_url` 场景可复制 `user_code`。
5. `auth_ui_capabilities` 成为 UI 菜单渲染单源；旧硬编码按钮矩阵被移除。
