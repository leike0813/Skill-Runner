# Change Proposal: run-observation-live-sequence-timeline

## Why

管理 UI 的 Run Observation 当前有聊天区与三流面板，但缺少一个 run-scope 的统一时序视图。  
在排查状态推进、鉴权与回复时，用户需要跨多个面板人工对齐时间点，成本高且容易误判。

## What Changes

1. 在管理 UI Run Observation 页底部新增默认折叠的 Run Timeline 区域。  
2. 新增管理 API：`GET /v1/management/runs/{request_id}/timeline/history`。  
3. 后端聚合 Orchestrator / RASP / FCMP / Chat / Client 五类事件到单一 run 时间线。  
4. 时间线按 `event.ts` 主序排序，缺失时间戳时按稳定回退键排序。  
5. 默认返回最近 100 条时间线事件，支持基于 cursor 的增量刷新。

## Non-Goals

1. 不修改 FCMP/RASP/chat 协议语义。  
2. 不修改现有 `/protocol/history`、`/chat/history` 接口行为。  
3. 不新增 SSE 通道。
