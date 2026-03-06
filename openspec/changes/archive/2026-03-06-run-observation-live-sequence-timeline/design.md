# Design: run-observation-live-sequence-timeline

## Overview

本 change 在管理 UI 的 Run Detail 页增加 run-scope 时间线面板，并新增管理端聚合接口。  
实现采用现有 3 秒轮询机制，不引入新的流式通道。

## Design Decisions

### 1. 时间线范围与主序

- 时间线范围为 **Run Scope**，覆盖该 run 的所有 attempts。  
- 主排序键为 `event.ts`。  
- 缺失 `ts` 时使用稳定回退序：`attempt ASC -> stream priority -> seq/local_seq -> ingest index`。  
- 生成 run 级 `timeline_seq` 作为时间线 cursor。

### 2. 五泳道固定模型

固定泳道：
1. `orchestrator`
2. `parser_rasp`
3. `protocol_fcmp`
4. `chat_history`
5. `client`

其中 `client` 来自：
- chat history 中 `role=user`
- FCMP 中关键客户端交互事件（`interaction.reply.accepted`、`auth.input.accepted`）

### 3. API 设计

- `GET /v1/management/runs/{request_id}/timeline/history`
- Query:
  - `cursor`（默认 0）
  - `limit`（默认 100，最大 500）
- Response:
  - `events[]`（含 `timeline_seq/ts/lane/kind/summary/attempt/source_stream/raw_ref?/details`）
  - `cursor_floor/cursor_ceiling/source`

### 4. UI 交互

- Run Timeline 区域默认折叠，位于 Raw stderr 区域之后。  
- 展开后渲染五泳道网格，每条事件展示摘要气泡。  
- 点击气泡可展开 details（含格式化 JSON）。  
- 有 `raw_ref` 时复用现有 raw_ref 预览跳转。  
- 首次加载读取最近 100 条；后续每 3 秒按 cursor 增量刷新。  
- 保持窗口内最近 100 条，支持“Load earlier”回看更早窗口。

## Validation

1. 后端聚合与排序单测覆盖 run-scope 与 cursor 增量。  
2. 管理路由单测覆盖参数透传与响应结构。  
3. 管理 UI 模板语义测试覆盖 timeline 折叠区与前端刷新逻辑。  
4. 管理页面集成测试覆盖 run detail 页面渲染与新接口引用。
