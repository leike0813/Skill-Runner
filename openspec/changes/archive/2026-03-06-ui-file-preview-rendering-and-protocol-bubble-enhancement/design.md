# Design: ui-file-preview-rendering-and-protocol-bubble-enhancement

## Scope

本 change 只处理 UI 渲染与可读性增强，后端协议与业务语义保持不变。

## Design Decisions

### 1. 预览渲染统一到平台服务

新增 `server/services/platform/file_preview_renderer.py` 作为统一入口，供：

- 管理 UI Skill Browser 文件预览
- 管理 UI Run Observation 文件预览
- E2E Run bundle 文件预览

复用同一套逻辑，避免多处重复实现导致行为漂移。

### 2. 预览响应向后兼容扩展

保留既有字段：

- `mode`
- `content`
- `size`
- `meta`

新增字段：

- `detected_format`: `markdown|json|text`
- `rendered_html`: 仅 markdown
- `json_pretty`: 仅 json

旧客户端忽略新增字段即可继续工作。

### 3. Markdown 渲染安全策略

服务端渲染链：

1. `markdown` 生成 HTML  
2. `bleach` 进行白名单清洗和 linkify

不允许原始危险标签/属性直接进入前端 DOM。

### 4. 三流视图默认摘要 + raw 开关

管理 UI `run_detail` 中 FCMP/RASP/Orchestrator 三个面板各自具备：

- 默认摘要气泡视图（高频事件专用摘要 + 通用回退摘要）
- `View raw` 勾选框（切换回 JSON 原文）

切换在前端完成，不改变后端历史接口。

### 5. E2E 文件预览滚动修复

将预览面板从“外层隐藏溢出”调整为“容器可滚动”，保证长内容可读。

## Risks and Mitigations

1. **XSS 风险**：通过服务端 `bleach` 清洗控制。  
2. **模板行为回归**：增加模板语义测试，检查关键分支字符串。  
3. **摘要映射遗漏**：未覆盖事件使用通用摘要，不阻断展示。

## Validation

1. 文件预览渲染单测覆盖 markdown/json/binary/too_large。  
2. E2E 模板语义测试覆盖滚动与格式分支。  
3. 管理 UI 模板/页面测试覆盖 raw toggle 与摘要渲染入口。
