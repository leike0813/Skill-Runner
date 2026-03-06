# Change Proposal: ui-stream-scroll-and-rich-preview-rendering

## Why

管理 UI 与 E2E 文件预览链路仍有几个可见问题：

1. 三流面板每轮刷新都会强制滚动到底部，用户无法稳定查看历史片段。  
2. Skill Browser 文件树缺少目录折叠，且三处文件树/预览实现分散。  
3. 文件预览虽已扩展格式检测，但 JSON/YAML/TOML/Python/JavaScript 的高亮链路未在所有页面端到端生效。  
4. Run Observation 页面中 Cancel 与 stderr 区域布局不合理，可读性和可操作性不足。

## What Changes

1. 三流面板改为“仅贴底时自动跟随”的滚动策略。  
2. RASP 摘要增强，补充工具回复类型、source 线索与关键状态字段。  
3. 三流摘要气泡支持点击展开详情（互斥手风琴），并保留 raw 模式切换。  
4. 新增共享 File Explorer 前端模块，统一管理 Run Observation、Skill Browser、E2E Run 三处文件树与预览交互。  
5. 文件预览高亮链路端到端打通：JSON/YAML/TOML/Python/JavaScript/Markdown。  
6. Run Observation 布局调整：三流窗口统一固定高度；stderr 区域改为三流下方全宽折叠区；Cancel Run 上移至状态区。

## Non-Goals

1. 不修改 FCMP/RASP/Orchestrator 协议语义。  
2. 不新增或删除 API 路径。  
3. 不扩展到 E2E 页面样式治理。
