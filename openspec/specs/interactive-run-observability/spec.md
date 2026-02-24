# interactive-run-observability Specification

## Purpose
TBD - created by archiving change interactive-30-observability-tests-and-doc-sync. Update Purpose after archive.
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
