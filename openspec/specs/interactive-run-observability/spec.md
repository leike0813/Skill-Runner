# interactive-run-observability Specification

## Purpose
定义 waiting_user 的可观测状态暴露和日志轮询建议区分策略。
## Requirements
### Requirement: 系统 MUST 暴露 waiting_user 的可观测状态
系统 MUST 在状态接口中明确体现 run 是否处于等待用户输入阶段。

#### Scenario: 查询 waiting_user 状态
- **GIVEN** run 当前在等待用户输入
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}`
- **THEN** 响应 `status=waiting_user`
- **AND** 包含当前待决交互标识（如 `pending_interaction_id`）

### Requirement: 日志轮询建议 MUST 区分 waiting_user 与 running
系统 MUST 在等待用户阶段关闭“继续轮询日志”的建议标志。

#### Scenario: waiting_user 的日志 tail
- **WHEN** 客户端调用 logs tail 接口且 run 状态为 `waiting_user`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `false`

#### Scenario: running 的日志 tail
- **WHEN** run 状态为 `running`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `true`

### Requirement: 文档 MUST 定义交互模式 API 时序
系统文档 MUST 提供 interactive 模式的 API 时序和错误处理建议。

#### Scenario: 文档覆盖 pending/reply 流程
- **WHEN** 开发者查阅 API 文档
- **THEN** 可获得 create -> pending -> reply -> resume -> terminal 的完整流程
- **AND** 文档明确说明本阶段仅支持 API 交互，不提供 UI 交互入口

### Requirement: 运行时观测协议层 MUST 通过 Adapter 提供引擎解析结果
系统 MUST 在构建 RASP/FCMP 事件时通过对应引擎 Adapter 获取 runtime 解析结果，而不是在通用协议层维护引擎分支解析逻辑。

#### Scenario: 观测服务构建事件时委托 Adapter 解析
- **WHEN** 观测服务为某 run attempt 构建 RASP 事件
- **THEN** 系统调用对应引擎 Adapter 的 runtime 解析接口获取标准解析结构

### Requirement: 通用协议层 MUST 保持引擎无关
系统 MUST 使通用协议层仅负责事件组装、通用去重和度量计算，不包含 codex/gemini/iflow/opencode 的专用解析分支。

#### Scenario: 协议层无引擎解析分支
- **WHEN** 审查通用协议层实现
- **THEN** 不存在按引擎名称分支的专用解析函数实现

### Requirement: 观测层落盘 MUST 进行协议 Schema 校验
系统 MUST 在写入 `events.jsonl` 与 `fcmp_events.jsonl` 前执行 schema 校验。

#### Scenario: FCMP 落盘校验
- **WHEN** 观测层写入 FCMP 事件
- **THEN** 每条事件通过 `fcmp_event_envelope` 校验

### Requirement: 历史读取 MUST 采用“读兼容”策略
系统 MUST 在读取历史时过滤旧不合规行并记录诊断日志。

#### Scenario: 旧历史兼容
- **WHEN** 历史文件中存在不合规行
- **THEN** 该行被跳过
- **AND** 合规行继续对外返回

### Requirement: Gemini parser MUST prefer batch JSON parse for runtime streams
Gemini runtime parser MUST 先尝试将当前 stdout/stderr 批次作为整段 JSON 解析，再回退到行级/fenced JSON 路径。

#### Scenario: stdout batch JSON detected
- **WHEN** stdout 包含可解析 JSON 文档
- **THEN** parser MUST 提取 `session_id` 与 `response`（若存在）
- **AND** parser MUST 产出结构化 payload 供 RASP `parsed.json` 事件使用

### Requirement: Gemini raw rows MUST be coalesced before RASP emission
Gemini parser 输出的 raw 行 MUST 在进入 RASP 构建前执行归并，避免逐行爆炸。

#### Scenario: large stderr burst
- **GIVEN** Gemini stderr 在单次 attempt 中产生大量连续文本行
- **WHEN** parser 输出 raw 行
- **THEN** raw 行 MUST 被归并为有限数量的块
- **AND** 行归并后的上下文顺序 MUST 保持稳定

### Requirement: FCMP/RASP protocol history MUST NOT trigger query-time rematerialization
`protocol/history` 的 FCMP/RASP 查询 MUST 不再在查询路径重建并覆盖审计事件文件。

#### Scenario: fetch protocol history for running run
- **GIVEN** run 正在运行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 仅消费 live journal 与已有 audit 镜像
- **AND** MUST NOT 在该查询路径调用 stdout/stderr 重算写盘。

### Requirement: terminal FCMP/RASP history MUST flush mirror before audit-only read
run 进入 terminal 后，服务 MUST 在读取 audit-only 历史前完成 live mirror drain。

#### Scenario: terminal transition with pending mirror writes
- **GIVEN** run 已进入 terminal，且镜像落盘任务仍在进行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 先等待 mirror flush 完成
- **AND** 再返回 audit-only 结果。

### Requirement: RASP raw rows MUST be coalesced for high-volume stderr bursts
在高频错误输出场景中，RASP raw 行 MUST 进行分块归并以降低事件数量与聚合成本。

#### Scenario: repeated stderr stack traces
- **GIVEN** 同 attempt 的 stderr 连续输出大量行
- **WHEN** 生成 RASP 事件
- **THEN** 服务端 MUST 将连续行归并为有限数量 `raw.stderr` 事件块
- **AND** 事件顺序 MUST 保持稳定

### Requirement: timeline aggregation MUST reuse cache when audit files are unchanged
`timeline/history` MUST 在审计文件未变更时复用已聚合结果，避免重复全量解析与排序。

#### Scenario: repeated polling without file changes
- **WHEN** 客户端在短周期内重复调用 `timeline/history`
- **AND** run 审计文件签名未变化
- **THEN** 服务端 MUST 复用缓存聚合结果

### Requirement: terminal protocol history MUST converge to audit-only source
在 run 进入 terminal 后，RASP/FCMP 历史查询 MUST 以审计文件为唯一来源，避免 live 增量残留造成终态漂移。

#### Scenario: terminal run protocol history
- **GIVEN** run 状态已是 `succeeded|failed|canceled`
- **WHEN** 客户端查询 `protocol/history`（`stream=rasp|fcmp`）
- **THEN** 返回 MUST NOT 混合 live journal 事件
- **AND** `source` MUST 为 `audit`

