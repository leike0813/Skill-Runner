## Design Overview

本 change 只覆盖 Gemini，但接口与模型按可复用方式设计：

1. Gemini parser batch-first JSON 解析  
先尝试整段 JSON 文档解析（stdout/stderr），成功则提取关键字段并生成结构化 payload；失败再走原有回退路径。

2. 新增 `parsed.json` RASP 事件  
在 RASP 构建阶段消费 parser 的 `structured_payloads`，发出 `parsed.json` 事件，保持 envelope 不变。

3. Gemini raw 分块归并  
仅对 Gemini parser 输出的 raw 行进行分块归并，边界规则与既有 raw 归并一致（Traceback/Exception/空行/JSON 原子行/阈值触发）。

4. 复杂 stderr 结构归并增强  
针对 `GaxiosError: [{...` 这类“前缀文本 + 内嵌 JSON/数组 + JS 堆栈”样式，coalescer 增加中行结构起点识别与括号闭合扫描，优先按整段异常块归并，减少 stack frame 碎片事件。

5. 管理 UI 摘要映射  
Run Detail 的 RASP 摘要视图增加 `parsed.json` 显示分支，默认展示 `stream + session_id + response/summary`。

## Compatibility

- 无路由变化；现有客户端可继续按 `events[]` 消费。
- `parsed.json` 为新增事件类型，不影响既有 `raw.*` / `agent.message.final` 语义。
- `raw.*.data.line` 保持 string 类型，兼容旧逻辑。
