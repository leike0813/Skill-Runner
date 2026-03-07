## Why

当前 UI 语言切换只依赖 `?lang=` 查询参数，跨页面导航后会回落到默认中文，导致多语言体验不稳定。  
同时，表格内按钮在窄视口下会自动换行并出现按钮轮廓塌陷，影响可读性与操作一致性。

## What Changes

- 修复管理 UI 与 E2E 客户端的语言切换持久化：选中语言后写入 `lang` cookie，并在后续页面继续生效。
- 优化语言切换链接生成，保留当前页面已有查询参数并仅替换 `lang` 键，避免导航时丢失页面状态参数。
- 在共享设计系统中强化表格按钮样式，避免按钮文字换行导致的视觉折叠问题。
- 对管理 UI 和 E2E 表格动作区增加最小布局约束，保证窄宽度下按钮保持单行可读。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ui-i18n`: 语言切换后必须跨页面保持，且语言选择链接需稳定保留现有查询参数。
- `ui-design-system`: 表格场景下按钮显示必须禁止文本折行并保持稳定轮廓。

## Impact

- Affected code:
  - `server/i18n.py`
  - `server/main.py`
  - `e2e_client/app.py`
  - `server/assets/templates/ui/partials/language_switcher.html`
  - `e2e_client/templates/language_switcher.html`
  - `server/assets/static/css/design-system.css`
  - 相关管理 UI / E2E 表格模板（如需补充动作区 class）
  - 对应单测（`test_ui_routes.py`、`test_e2e_example_client.py` 或语义测试）
- API impact: None.
- Protocol impact: None.
