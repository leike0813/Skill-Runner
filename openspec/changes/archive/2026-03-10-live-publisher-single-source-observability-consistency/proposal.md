## Why

当前 FCMP/RASP 存在“live 发布 + 查询时重算 materialize”双轨并存。  
在 run 从 running 切到 terminal 时，`protocol/history` 会切换到 audit-only，可能出现事件集合回退（例如 timeline 数量下降）。

## What Changes

- 将 FCMP/RASP 观测收敛为 `live_publish` 唯一发布源。
- 审计文件仅作为 live publisher 的实时镜像落盘，不再由查询链路触发重算覆盖。
- `list_protocol_history(stream=fcmp|rasp)` 在 terminal 前执行 mirror flush，确保 terminal audit 可见最新 live 事件。
- 保留历史 `_materialize_protocol_stream` 能力用于离线维护，但不再由查询链路自动调用。

## Impact

- 无新增/删除 API 路径。
- `protocol/history` 响应结构不变，行为更稳定：running 与 terminal 口径不再出现集合回退。
- 历史旧 run 不自动迁移；本 change 保障新 run 与后续 run 一致性。
