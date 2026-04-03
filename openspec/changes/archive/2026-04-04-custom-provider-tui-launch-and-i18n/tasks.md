## 1. OpenSpec

- [x] 1.1 创建 `custom-provider-tui-launch-and-i18n` change 工件
- [x] 1.2 补齐 proposal / design / delta specs

## 2. UI and TUI launch

- [x] 2.1 在 custom provider 表格操作列新增 provider-row 级 `启动TUI`
- [x] 2.2 让 `/ui/engines/tui/session/start` 与 `ui_shell_manager.start_session()` 支持可选 `custom_model`

## 3. Claude provider-backed session injection

- [x] 3.1 让 Claude `ui_shell` session 配置支持 `provider/model` 注入
- [x] 3.2 保持普通 TUI 启动路径不回退

## 4. Localization and validation

- [x] 4.1 补齐 custom provider 相关 locale key
- [x] 4.2 更新 UI / route / ui_shell 回归测试
- [x] 4.3 运行目标 pytest 与 mypy

