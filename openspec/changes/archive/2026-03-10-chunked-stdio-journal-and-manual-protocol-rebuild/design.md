## Design Overview

本 change 将“运行期标准输出捕获”拆成两条并行审计产物：

1. 人类可读日志（现状保留）  
- `.audit/stdout.<N>.log` / `.audit/stderr.<N>.log`

2. 无损块日志（新增）  
- `.audit/io_chunks.<N>.jsonl`，每条记录一个实时读取到的 chunk（stdout/stderr）。

### 1) io_chunks 记录模型

每行 JSON 对象字段：
- `seq`: attempt 内单调递增序号（跨 stdout/stderr 共用一个序列）
- `ts`: UTC ISO8601 时间戳
- `stream`: `stdout|stderr`
- `byte_from`: 该 stream 内字节起点（闭区间起点）
- `byte_to`: 该 stream 内字节终点（开区间终点）
- `payload_b64`: 原始 bytes 的 base64 文本
- `encoding`: 固定 `base64`

该文件用于重构真相，不用于直接 UI 显示。

### 2) 写入路径

`BaseExecutionAdapter` 在读取子进程 stream chunk 时，同时执行：
- append 到 `stdout/stderr` 明文日志
- append 一条 `io_chunks` JSONL
- 继续保留当前 live emitter 调用

确保运行中可观测性不回退。

### 3) 手动协议重构

新增 `RunObservabilityService.rebuild_protocol_history(request_id)`：
- 按 run 的全部 attempts 逐个重构
- 固定 `rebuild_mode="strict_replay"`（不提供 canonical / forensic best-effort 分支）
- 先备份现有审计协议文件：
  - `events.<N>.jsonl`
  - `fcmp_events.<N>.jsonl`
  - `parser_diagnostics.<N>.jsonl`
  - `protocol_metrics.<N>.json`
  - `orchestrator_events.<N>.jsonl`
- 备份目录：`.audit/rebuild_backups/<timestamp>/attempt-<N>/`
- 重构输入固定为：
  1. `io_chunks.<N>.jsonl`
  2. `orchestrator_events.<N>.jsonl`
  3. `meta.<N>.json`
- 任一关键证据缺失/损坏：该 attempt 失败并返回原因，不覆写该 attempt 审计文件。
- 重构按运行时真实链路回放：
  - `on_process_started -> on_stream_chunk -> on_process_exit`
  - parser/raw 抑制逻辑与 live 统一
  - orchestrator 事件按原 `ts` 进入同一发布排序门禁
- 禁止重构期补偿注入（含 meta-backed 派生）。

### 4) 管理 API 与 UI

新增接口：
- `POST /v1/management/runs/{request_id}/protocol/rebuild`

返回包含：
- `request_id`, `run_id`
- `mode`（固定 `strict_replay`）
- `attempts`（每轮 `source/success/written/reason/event_count/diagnostics`）
- `backup_dir`
- `success`

Run Detail 页面新增“重构协议”按钮：
- 手动触发 API
- 不影响页面自动轮询逻辑
- 执行后展示结果并刷新三流面板。

### 5) 安全与兼容

- 不新增自动重构，避免页面访问引入重计算负担。
- 关键证据缺失或 journal 解析异常时 attempt 失败，并在结果中返回诊断（不覆写）。
- stdin 本次不纳入 io_chunks（保持现状）。
