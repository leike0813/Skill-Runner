## Why

管理 UI 的 Run Detail 在大体量错误输出场景下会出现明显卡顿，甚至拖慢同服务其他请求。根因有两类：
- RASP `raw.stderr/raw.stdout` 事件按行发射，容易出现事件爆炸；
- 页面与后端聚合链路在固定轮询下重复做高成本全量读取与排序。

## What Changes

- 引入 RASP raw 事件分块归并，降低事件数量与序列化开销。
- live 与 audit 共享同一 raw canonicalizer，避免双轨规则导致结果漂移。
- 为管理端 `protocol/history` 增加可选 `limit` 限流参数（默认 200，最大 1000）。
- `timeline/history` 增加基于 run 审计文件签名的服务端缓存，避免重复全量聚合。
- 管理 UI Run Detail 调整为 timeline 懒加载与折叠停刷，并在三流请求上带 `limit=200`。
- run terminal 后，`protocol/history(stream=rasp|fcmp)` 强制 `audit-only`，不再混合 live journal。
- 同步更新 API 文档与测试守卫。

## Impact

- Public API: `GET /v1/management/runs/{request_id}/protocol/history` 新增可选 `limit`。
- 协议语义：`raw.stderr/raw.stdout` 事件类型不变，`data.line` 可能为多行归并文本。
- 终态观测语义：terminal 阶段返回 `source=audit`，保证终态一致性。
