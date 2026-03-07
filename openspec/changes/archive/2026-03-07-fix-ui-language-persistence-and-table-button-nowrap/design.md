## Context

语言中间件已支持 `query > cookie > accept-language > default` 的解析顺序，但当前语言切换组件只拼接 `?lang=`，并未在响应中回写 cookie，导致跨页面时常回落到默认语言。  
按钮样式由共享设计系统提供，但 `.btn` 在表格窄列下允许文本换行，触发按钮高度异常和边框折叠。

## Goals / Non-Goals

**Goals**
- 让管理 UI 与 E2E 客户端语言切换在跨页面导航中稳定保持。
- 保持现有路由结构不变，仅修复语言状态保持链路。
- 统一修复表格按钮换行折叠问题，保证窄视口可读性。

**Non-Goals**
- 不新增语言类型或翻译文案。
- 不改 FCMP/RASP/后端业务 API。
- 不重构整套导航样式，仅修复按钮折行与基础布局约束。

## Decisions

### 1) 语言持久化采用 middleware 统一写 cookie

- 当请求携带有效 `?lang=` 时，响应统一写入 `lang` cookie（`path=/`）。
- 该逻辑在 `server/main.py` 与 `e2e_client/app.py` 的 i18n middleware 同步实现。
- 解析优先级保持不变（query 优先），仅补持久化行为。

### 2) 语言切换链接保留现有 query 参数

- 语言切换模板不再使用 `request.url.path + ?lang=` 的拼接方式。
- 改为使用请求 URL 的 query dict 构建链接：保留原有参数，仅覆盖 `lang`。

### 3) 表格按钮防折行收敛到设计系统

- 在共享样式中为表格动作按钮增加约束：
  - `white-space: nowrap`
  - `display: inline-flex`
  - `align-items: center`
- 需要并排按钮的表格动作区使用轻量容器 class（例如 `.table-actions`）控制 `gap` 与换行策略。

## File Changes

- **新增/修改（规格）**
  - `openspec/changes/fix-ui-language-persistence-and-table-button-nowrap/specs/ui-i18n/spec.md`
  - `openspec/changes/fix-ui-language-persistence-and-table-button-nowrap/specs/ui-design-system/spec.md`
- **修改（实现）**
  - `server/main.py`
  - `e2e_client/app.py`
  - `server/assets/templates/ui/partials/language_switcher.html`
  - `e2e_client/templates/language_switcher.html`
  - `server/assets/static/css/design-system.css`
  - 必要的管理 UI / E2E 表格模板（动作区 class 对齐）
- **修改（测试）**
  - `tests/unit/test_ui_routes.py`
  - `tests/api_integration/test_e2e_example_client.py`
  - 如需：`tests/unit/test_e2e_run_observe_semantics.py`

## Risks / Trade-offs

- [Risk] 写 cookie 可能影响无状态缓存策略。  
  → Mitigation: 仅在请求显式带 `lang` 参数时写入；不强制每次响应都写 cookie。

- [Risk] 全局按钮样式改动可能影响非表格按钮。  
  → Mitigation: 将 nowrap 约束限定在表格上下文（`.table .btn` / `.table-actions .btn`）。

## Validation

- 打开任一页面切换语言后跳转到其他页面，语言不回落。
- 在窄浏览器宽度下，表格按钮不出现多行折叠。
- 现有路由与功能不回归。
