## Why

当前 run 审计保留了 `.audit/stdout.<N>.log` / `.audit/stderr.<N>.log`，但它们是拼接后的连续文本，缺少“每次子进程输出块”的边界信息。  
当 parser / 协议语义演进时，无法稳定重放原始 chunk 边界来重构 RASP/FCMP，重建能力不足。

另外，管理 UI 当前默认走审计回放；我们需要一个显式的、人工触发的“协议重构”入口用于运维和升级后补重建，而不是页面访问自动重构。

## What Changes

1. 在 attempt 审计中新增并行无损 chunk journal：`.audit/io_chunks.<attempt>.jsonl`（stdout/stderr，base64 payload）。
2. 保留现有可读 `stdout/stderr` 明文日志，不替换、不删除。
3. 新增 run 级手动协议重构 API：`POST /v1/management/runs/{request_id}/protocol/rebuild`。
4. 新增管理 UI Run Observation “重构协议”按钮，手动触发并显示结果。
5. 协议重构器固定为 strict replay only：必须按真实运行链路回放，关键证据缺失时 attempt 失败且不覆写；写回前自动备份旧审计文件。
6. 重构禁止补偿注入：仅允许真实回放自然产出事件，不进行 meta-backed 派生补偿。
7. 页面常规读取逻辑不变：仍是审计回放，不自动重构。

## Impact

- 新增管理 API（仅 management 命名空间），不影响现有业务 API 路径。
- `.audit/` 合同增量新增 `io_chunks.<attempt>.jsonl`。
- 可观测能力增强：提供长期可重构的原始 chunk 真相源。
