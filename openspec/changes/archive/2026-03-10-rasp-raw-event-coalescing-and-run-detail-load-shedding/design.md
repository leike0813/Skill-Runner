## Design Overview

本 change 采用“后端减量 + 前端减压”的双向方案：

1. RASP raw 行归并  
在 `build_rasp_events` 与 live publish 中统一复用 raw canonicalizer，对连续同源 raw 行进行分块归并，保留事件顺序与原始定位能力（块级 `raw_ref`）。

2. 协议历史限量读取  
管理端 `protocol/history` 增加 `limit`，默认返回最近窗口，增量模式下做上限截断。

3. 时间线聚合缓存  
`timeline/history` 以 run 审计文件签名（size + mtime）做缓存键；签名不变时直接复用聚合结果。

4. Run Detail 轮询削峰  
timeline 默认折叠不初始化不轮询；展开后才拉取并增量刷新。三流轮询请求统一带 limit。

5. 终态强一致收敛  
run terminal 后 `protocol/history(stream=rasp|fcmp)` 强制 `audit-only`。live 仅用于运行期增量观测，终态结果以审计重建为准。

6. 稳定键去重  
RASP live/audit 合流时按稳定键（attempt + stream + byte range + type + category）去重，避免同语义事件重复显示或排序漂移。

## Raw Coalescing Rules

- 仅归并 `raw.stderr` 与 `raw.stdout`（`pty` 不参与本次归并）。
- 同 attempt + 同 stream + 相邻行可归并。
- 触发 flush 条件：
  - 空行；
  - 匹配边界前缀：`Traceback` / `Exception` / `Error:` / `Caused by:`；
  - 匹配堆栈帧样式（如 `File "...", line`、`at ...`）；
  - 单行完整 JSON（保持原子，不跨边界）；
  - 超过 `max_lines_per_block=24` 或 `max_chars_per_block=8192`。

## Compatibility

- 事件类型与外层 envelope 不变；
- `data.line` 仍为 string（向后兼容）；
- 新增 `limit` 为可选参数，旧调用不受影响。
- terminal 阶段的 `source` 固定为 `audit`（行为收敛，不改响应结构）。
