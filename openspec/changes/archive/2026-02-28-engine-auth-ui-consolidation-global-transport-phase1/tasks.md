## 1. OpenSpec

- [x] 1.1 新建 change 四工件与 3 份 delta spec
- [x] 1.2 运行 `openspec validate engine-auth-ui-consolidation-global-transport-phase1 --type change`

## 2. Backend Context

- [x] 2.1 在 `server/routers/ui.py` 增加 `auth_ui_capabilities` 计算与模板注入
- [x] 2.2 OpenCode provider 列表与能力矩阵联动（provider/auth_mode 映射）

## 3. UI Templates

- [x] 3.1 `engines_table.html` 改为每引擎单鉴权入口按钮
- [x] 3.2 `engines.html` 增加全局 transport 下拉并在会话中禁用
- [x] 3.3 `engines.html` 引入分层弹出菜单（非 OpenCode 二级，OpenCode provider->方式）
- [x] 3.4 主鉴权状态区移除启动按钮，仅保留取消按钮
- [x] 3.5 为 codex/opencode+openai `auth_code_or_url` 的 `user_code` 增加复制按钮
- [x] 3.6 输入提示文案按引擎/provider/方式细化

## 4. Tests & Docs

- [x] 4.1 更新 `tests/unit/test_ui_routes.py` 断言（新入口结构、全局 transport、能力矩阵）
- [x] 4.2 更新 `docs/e2e_example_client_ui_reference.md`
- [x] 4.3 更新 `docs/api_reference.md`
- [x] 4.4 更新 `docs/containerization.md`
