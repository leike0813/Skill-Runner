# running-protocol-history-live-first-hotpath

## Why

运行中 run 的详情页会持续轮询 `/v1/management/runs/{id}/protocol/history`。当前实现中：

- `stream=fcmp` 会在热路径里执行 `reindex_fcmp_global_seq(run_dir)`
- `stream=fcmp` / `stream=rasp` 都会整份读取对应 audit JSONL
- chat 历史主要依赖 live journal，因此表现为 chat 能继续推进，但 FCMP / RASP history 更容易卡死或严重滞后

这会把运行中 protocol 面板的读取放到重 IO / 重校验路径上，并直接拖慢 uvicorn 的请求处理。

## What Changes

- 为运行中 current attempt 的 FCMP / RASP history 增加 live-first fast path
- 命中 fast path 时，直接返回 live journal payload，不读取 audit JSONL，不触发 FCMP reindex
- terminal run 和非 current attempt 的查询保持现有 audit 语义
- 不修改 UI 调用方式，不修改 chat / FCMP / RASP 事件结构

## Impact

- 活跃 run 期间，protocol 面板初次加载和轮询会显著更轻
- chat / FCMP / RASP 的返回结构保持不变
- terminal fallback、历史 attempt 查询、orchestrator stream 均保持原行为
