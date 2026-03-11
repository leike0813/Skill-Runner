## Why

当前文件预览和时间展示仍有两个稳定缺陷：一是管理 UI / E2E 页面收到的部分时间字段仍是无时区 ISO 字符串，浏览器会将其视为本地时间，导致“本地时区渲染”实际上没有生效；二是 `.jsonl` 预览并未真正支持，且很多可显示文本文件仍缺少统一行号。

这两个问题都属于展示真源不一致：时间没有统一输出 UTC 语义，文件预览也没有以统一 `rendered_html` 作为前端唯一消费口径。现在需要一次收口，避免 UI 继续分叉。

## What Changes

- 统一管理 UI / E2E run 页面相关时间字段的输出口径：后端返回带 UTC 语义的 ISO 时间，前端继续按浏览器本地时区渲染。
- 为文件预览新增真正的 `.jsonl` 渲染支持，而不是误判为 `.json` 后整体解析失败再回退。
- 后端文件预览统一为除 Markdown 外的所有可显示文本格式生成可复用的 `rendered_html`，包含行号。
- 管理 UI、Skill Browser、E2E 文件预览统一优先消费后端 `rendered_html`，不再各自维护格式白名单。
- 明确 Markdown 继续使用富文本渲染，不追加源码行号。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `run-observability-ui`: Run 观测页面的时间展示与 run 文件预览需要支持本地时区和带行号的 `jsonl/text` 预览。
- `builtin-e2e-example-client`: E2E runs 列表与 run observation 页面需要按本地时区展示时间，并消费统一的带行号文件预览。
- `ui-skill-browser`: Skill Browser 文件预览需要支持 `jsonl` 和统一的带行号文本预览。

## Impact

- Affected code:
  - `server/routers/jobs.py`
  - `server/routers/management.py`
  - `server/routers/ui.py`
  - `server/services/platform/file_preview_renderer.py`
  - `server/assets/static/js/file_explorer.js`
  - `server/assets/templates/ui/partials/file_preview.html`
  - `e2e_client/templates/partials/file_preview.html`
  - `server/assets/templates/ui/runs.html`
  - `e2e_client/templates/runs.html`
  - `server/locales/*.json`（仅当需要补 `jsonl` 标签）
- API impact:
  - 无新路由、无删路由。
  - 现有时间字段序列化口径更严格，输出为带 UTC 语义的 ISO 字符串/时间对象。
  - 文件预览 payload 继续兼容现有结构，仅新增/稳定使用 `detected_format=jsonl` 与 `rendered_html`。
