# ndjson-live-overflow-repair-and-resync Design

## Design Overview

本次 change 在公共层引入两部分能力：

1. `NdjsonLineBuffer`
   - 统一管理每个 stream 的逻辑行起点、累计字节数、受限前缀和 overflow 状态
   - 超过 `4096` bytes 后停止继续扩张正文缓冲，只保留前缀并等待换行或 `finish()`
2. 通用 JSON 修复器
   - 对受限前缀做词法级修复，补齐字符串、对象、数组和最小合法值
   - 输出必须是可被 `json.loads()` 解析的 `dict`

parser 与 raw publisher 都复用这套公共能力，不再各自维护独立的大字符串缓冲逻辑。

## Shared Overflow Guard

- 阈值固定为 `4096` bytes，按单条逻辑行、按 stream 独立计算
- 未超限时：保持正常逐行处理
- 超限后：
  - 不再继续保留新增正文
  - 只累计真实 `byte_to`
  - 等待换行或进程退出时统一 finalize
- finalize 时：
  - 如果未超限，直接返回原行
  - 如果超限，进入 repair 流程

这样可以切断“chunk 到来就重新拼接整个超长行”的热路径，同时保留真实 `raw_ref.byte_from/byte_to` 范围。

## Generic JSON Repair

修复器只依赖 JSON 文本，不依赖引擎 schema。

修复策略：

- 去掉尾部 `\r\n`
- 若原前缀本身已是合法 `dict`，直接返回
- 否则做有限 trim + 词法扫描：
  - 跟踪是否在字符串内、escape 状态、对象/数组栈
  - 若停在未闭合字符串内，追加统一截断标记并闭合字符串
  - 若停在 `:` 之后或需要 value 的位置，补 `null`
  - 若存在未闭合对象/数组，按栈顺序补 `}` / `]`
- 仅当修复结果 `json.loads()` 后是 `dict` 才视为成功

截断标记固定为：

- ` ... [truncated by live overflow guard]`

这样能尽量保住：

- 顶层 `type`
- 各类 message / part / item 的结构
- `tool_use_id`、`session_id`、`message_id`、`callID` 等前置字段

## Live Publisher Integration

- parser 路径：
  - 对 repaired 行先发 `diagnostic`
  - 再把修复后的 `dict` 交给现有引擎 row handler
- raw 路径：
  - 超长行不再发布原始巨型 `raw.stdout`
  - 改为发布修复后的单行 JSON 文本
- unrecoverable 时：
  - 只发 warning
  - 不为该行产出 semantic event
  - 换行后继续处理后续行

## Compatibility

- 不新增新的 `LiveParserEmission.kind`
- 不修改 `RuntimeStreamParseResult` 字段形状
- 不修改 FCMP / RASP 类型名
- 新增的仅是 `diagnostic.warning` code：
  - `RUNTIME_STREAM_LINE_OVERFLOW_REPAIRED`
  - `RUNTIME_STREAM_LINE_OVERFLOW_UNREPAIRABLE`
