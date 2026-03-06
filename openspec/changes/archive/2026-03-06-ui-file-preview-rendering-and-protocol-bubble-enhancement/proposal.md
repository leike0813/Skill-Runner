# Change Proposal: ui-file-preview-rendering-and-protocol-bubble-enhancement

## Why

当前 UI 存在三类可用性问题：

1. E2E Run 页面文件预览在长内容下无法滚动，影响可读性。  
2. 文件预览仅展示纯文本，缺少 Markdown / JSON 的可读渲染。  
3. 管理 UI 的 FCMP / RASP / Orchestrator 面板长期只显示原始结构化数据，关键信息噪声高，定位效率低。

这些问题都属于展示层能力缺失，不需要改动 FCMP/RASP 协议语义和 API 路径。

## What Changes

1. 新增统一文件预览渲染服务，支持 Markdown 安全渲染、JSON pretty 渲染。  
2. 扩展文件预览 payload（增量字段）：`detected_format`、`rendered_html`、`json_pretty`。  
3. 修复 E2E 文件预览容器滚动行为。  
4. 管理 UI 三流面板新增“摘要气泡视图（默认）+ raw 切换（按面板独立）”。  
5. 增加相关 i18n 文案与测试覆盖。

## Non-Goals

1. 不修改 FCMP/RASP/orchestrator 事件生成逻辑。  
2. 不新增或重命名 API 路由。  
3. 不引入前端第三方 CDN 依赖。  
4. 不改动状态机与运行时协议合同。
