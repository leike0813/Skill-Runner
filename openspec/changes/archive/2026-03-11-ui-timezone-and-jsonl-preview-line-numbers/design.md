## Context

当前前端时间本地化逻辑本身已经存在，但后端部分链路返回的是 naive ISO 时间，浏览器会把它直接按本地时间解释，因此不会发生预期的 UTC→本地时区转换。问题集中在 run 相关页面的首屏模板注入与状态接口序列化链路。

文件预览方面，后端已经有 Markdown / JSON / YAML / TOML / Python / JavaScript 的基础渲染能力，但 `.jsonl` 仍被误归类为 `json`，随后整文件 `json.loads` 失败而退化为纯文本。同时，前端消费 `rendered_html` 还依赖一份格式白名单，导致即使后端已经生成了可复用的带行号 HTML，也不会在所有页面生效。

## Goals / Non-Goals

**Goals:**
- 让 run 相关页面的时间统一以“后端输出 UTC 语义、前端按浏览器本地时区渲染”的方式工作。
- 让 `.jsonl` 成为真正的一等预览格式。
- 让除 Markdown 外的所有可显示文本预览都统一具备行号。
- 让管理 UI、Skill Browser、E2E 三处文件预览共享同一后端预览真源，消除格式白名单分叉。

**Non-Goals:**
- 不修改时间存储层格式；本次只修读出/序列化边界。
- 不改变 Markdown 的富文本渲染模式，不把它切回源码视图。
- 不新增 HTTP 路由或改变文件预览接口基本形状。

## Decisions

### 1) 在路由边界统一将 naive 时间解释为 UTC

选择在 `jobs.py`、`management.py`、`ui.py` 这些直接面向前端的边界做归一化，而不是回头批量改写所有存储层的历史 `datetime.utcnow().isoformat()` 调用。

原因：
- 本次问题是展示失真，不是存储不可读。
- 读边界修复可以立即覆盖新旧数据。
- 改存储层会牵涉更大范围回归，不适合作为本次 UI 修补。

替代方案：
- 全仓库统一把写入都改成 `timezone.utc` aware ISO。
  - 未选用：这是后续可做的清理，但不是当前最小闭环。

### 2) `.jsonl` 单独检测并逐行渲染

`.jsonl` 不再走整文件 JSON 解析，而是按“逐行 JSON 文档集合”处理：
- 每一行可解析 JSON 时做稳定 pretty。
- 空行保留为空行。
- 不合法行保留原文本，以保证预览容错。

原因：
- 这是 JSONL 的真实语义。
- 可兼顾可读性与容错，不要求整文件完全合法。

### 3) `rendered_html` 成为非 Markdown 文本预览的统一前端消费真源

后端会为 `json/jsonl/yaml/toml/python/javascript/text` 统一生成带行号的 `rendered_html`。前端改为“只要有 `rendered_html` 就优先渲染”，而不是维持一份格式白名单。

原因：
- 行号、高亮、背景修复都应由后端单点控制。
- 可以避免管理 UI / E2E / Skill Browser 各自维护一套格式分支。

替代方案：
- 前端按 `detected_format` 继续白名单判断。
  - 未选用：这正是当前分叉根因。

### 4) Markdown 保持富文本，不加源码行号

按已确认决策，Markdown 继续显示渲染后的富文本内容，不再为它附加源码行号。

原因：
- Markdown 的渲染高度与源文本行数天然不对齐，强加行号只会制造误导。
- 需求重点是“所有可显示文本类预览”，Markdown 作为语义渲染例外单独保留更合理。

## Risks / Trade-offs

- [Risk] 仍存在部分非 run 页面继续输出 naive 时间。
  - Mitigation: 本次先修 run 相关主链路；后续若需要，可把 UTC 归一化 helper 提升为共享工具。
- [Risk] JSONL 容错渲染会让非法行看起来不像严格 JSON。
  - Mitigation: 保留原始文本，不伪装为结构化成功。
- [Risk] 所有文本都走 `rendered_html` 后，前端样式差异可能暴露旧 CSS 问题。
  - Mitigation: 继续复用现有 `preview-rich/preview-markdown` 样式容器，避免重新发明结构。

## Migration Plan

1. 先补 OpenSpec delta specs，固定“本地时区 + jsonl/行号”行为要求。
2. 后端补时间归一化与 `.jsonl`/text 渲染。
3. 前端三处消费逻辑统一切到 `rendered_html` 优先。
4. 跑 UI 相关单测和集成测试，确认无回归。

## Open Questions

- 无。当前范围和例外项（Markdown 无行号）已明确。
