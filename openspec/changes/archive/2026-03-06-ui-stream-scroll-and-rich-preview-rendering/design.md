# Design: ui-stream-scroll-and-rich-preview-rendering

## Overview

本 change 只改展示层，不改协议语义。实现重点是：

1. 三流滚动行为从“强制贴底”改为“贴底才跟随”。  
2. 协议摘要视图增强 + 详情展开交互。  
3. 文件树/预览统一模块化，三处页面复用同一交互实现。  
4. 管理 UI 文件预览统一高对比容器和多格式高亮渲染。  
5. Run Observation 布局统一（三流固定高度 + stderr 折叠 + Cancel 上移）。

## Design Decisions

### 1. Stream Auto-Follow

- 维护每个流面板独立的 `autoFollow` 状态。  
- 用户滚动离开底部后，刷新仅更新内容，不调整 `scrollTop`。  
- 仅当当前处于贴底阈值（例如 24px）内时，刷新完成后自动滚到底部。  
- raw 视图与摘要视图共享同一判定逻辑。

### 2. Protocol Bubble Drilldown

- 三流面板摘要气泡新增点击展开详情。  
- 展开模式使用互斥手风琴：同一面板同时只展开一条。  
- 详情区包含：
  - 关键字段摘要（type/category/source/status/code 等）  
  - 完整 JSON 结构（格式化）  
  - raw_ref 跳转按钮（若该行存在）

### 3. RASP Summary Enrichment

- `summarizeProtocolRow("rasp", row)` 增加：
  - `event.category/type`
  - `source.engine/parser`
  - `code/status/message/line`（按可用字段）
- 工具回复类型标签映射：
  - `raw.*` -> tool-output  
  - `lifecycle.*` -> lifecycle  
  - `interaction.*` -> interaction  
  - `diagnostic.*` -> diagnostic  
  - `agent.*`/`assistant.*` -> agent  
  - `auth.*` -> auth  
  - 其他 -> other

### 4. Rich File Preview Rendering

- 扩展文件格式识别：`json|yaml|toml|python|javascript|markdown|text`。  
- markdown 继续走安全渲染。  
- 代码和结构化文本走服务端高亮 HTML（pygments）；失败时回退纯文本。  
- 预览响应保持向后兼容，新增字段仅为可选增强。

### 5. Preview Contrast and Scroll

- Skill Browser 预览区改固定高度滚动容器，尺寸与 Run Observation 对齐。  
- 管理 UI 两处预览统一高对比样式（深色正文、白底、清晰边框）。

### 6. Shared File Explorer Module

- 新增静态模块（`/static/js/file_explorer.js`）作为三处页面统一文件树/预览交互实现。  
- 模块职责：
  - 树渲染与默认目录折叠
  - 文件点击预览请求调度
  - 预览渲染分支（rendered_html / json_pretty / plain text）
  - 失败与空态提示
- 页面仅传入 entries/provider 与文案配置，避免重复实现漂移。

### 7. Run Observation Layout Refinement

- 三流窗口在摘要/raw 两种模式均固定同一高度。  
- Raw stderr 区域移到三流下方，全宽、默认折叠；折叠状态有输出时显示红点提示。  
- Cancel Run 按钮上移到状态信息区，避免与日志区域抢占视觉焦点。

## Validation

1. 单测覆盖格式识别和高亮回退。  
2. 模板语义测试覆盖手风琴结构与 autoFollow 逻辑关键代码。  
3. 管理 UI 页面集成测试覆盖新控件存在性与页面可达性。
