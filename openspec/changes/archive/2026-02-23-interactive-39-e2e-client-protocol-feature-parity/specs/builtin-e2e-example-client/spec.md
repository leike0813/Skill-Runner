## MODIFIED Requirements

### Baseline Clarification
以下能力在当前代码基线中已具备，并作为本 change 的前置能力：
- source-aware 双链路映射（installed:`/v1/jobs/*`，temp:`/v1/temp-skill-runs/*`）
- `events/history` 与 `logs/range` 代理端点
- fixture skill 动态打包并走临时 skill 执行链路

本 change 的主要增量集中在：
- Run 观测页增强（`raw_ref` 回跳、relation 视图、low-confidence 标识）
- 录制/回放协议定位摘要（`cursor`、关键事件、`raw_ref` 摘要）

### Requirement: 示例客户端 Run 观测页 MUST 对齐最新协议能力
示例客户端 Run 观测页 MUST 在现有 SSE/FCMP 基础上，支持协议增强能力：历史补偿、`raw_ref` 回跳、事件关联视图与低置信度展示。

#### Scenario: FCMP-first + 低置信度可视化
- **WHEN** 客户端收到 `chat_event` 与 `run_event`
- **THEN** 主对话区优先渲染 `chat_event`
- **AND** 当关联 `run_event.source.confidence < 0.7` 时展示低置信度标识

#### Scenario: raw_ref 回跳预览
- **WHEN** 某条消息包含 `raw_ref`
- **THEN** 用户可点击该引用触发日志区间读取
- **AND** 页面展示对应 `stream/byte_from/byte_to` 的原始片段

#### Scenario: 事件关联视图
- **WHEN** 客户端接收结构化事件
- **THEN** 页面展示基于 `seq/correlation` 的最小关联视图
- **AND** 用户可从关联节点回跳消息或事件位置

### Requirement: 示例客户端 API 代理 MUST 支持历史与区间日志能力
示例客户端代理层 MUST 暴露与后端协议一致的历史事件和日志区间读取能力，供观测页调用。

#### Scenario: 历史事件查询代理
- **WHEN** 客户端请求 `GET /api/runs/{request_id}/events/history`
- **THEN** 代理根据 `run_source` 转发到对应 run 链路 API（installed:`/v1/jobs/*`，temp:`/v1/temp-skill-runs/*`）
- **AND** 支持 `from_seq/to_seq/from_ts/to_ts` 区间参数

#### Scenario: 日志区间读取代理
- **WHEN** 客户端请求 `GET /api/runs/{request_id}/logs/range`
- **THEN** 代理根据 `run_source` 转发到对应 run 链路 API（installed:`/v1/jobs/*`，temp:`/v1/temp-skill-runs/*`）
- **AND** 支持 `stream/byte_from/byte_to` 参数

### Requirement: 示例客户端 run 读/交互代理 MUST 使用 source-aware 双链路映射
示例客户端 MUST 按 `run_source` 将 run 状态、交互、事件、历史、日志区间、结果、产物与 bundle 统一映射到 jobs/temp 两条链路，不使用 management run 读路径作为默认实现。

#### Scenario: Installed source maps to jobs endpoints
- **WHEN** `run_source=installed`
- **THEN** 代理请求 `/v1/jobs/{request_id}` 及其子路径（含 `pending/reply/events/history/logs/range/result/artifacts/bundle`）
- **AND** 行为语义与客户端展示保持一致

#### Scenario: Temp source maps to temp-skill-runs endpoints
- **WHEN** `run_source=temp`
- **THEN** 代理请求 `/v1/temp-skill-runs/{request_id}` 及其子路径（含 `pending/reply/events/history/logs/range/result/artifacts/bundle`）
- **AND** 行为语义与 installed 链路保持同构

### Requirement: 示例客户端录制回放 MUST 记录协议定位摘要
示例客户端录制模型 MUST 记录可用于协议级回放定位的摘要字段（如 `cursor`、关键事件摘要、`raw_ref` 摘要）。

#### Scenario: 录制包含协议定位摘要
- **WHEN** 用户执行 run 观测和交互
- **THEN** 录制文件保留关键协议摘要信息
- **AND** 回放页可展示这些摘要用于定位关键步骤

### Requirement: 示例客户端 MUST 支持 fixture skill 走临时 skill 执行链路
示例客户端 MUST 支持从 `tests/fixtures/skills` 读取 skill 包，在运行时动态打包并通过 `/v1/temp-skill-runs` 两步接口创建 run。

#### Scenario: fixture skill 动态打包并创建 temp run
- **WHEN** 用户在客户端选择 fixture skill 并提交执行表单
- **THEN** 客户端先调用 `POST /v1/temp-skill-runs`
- **AND** 再调用 `POST /v1/temp-skill-runs/{request_id}/upload` 上传动态打包的 `skill_package`（可附带输入 zip）

#### Scenario: temp run 可从客户端重进并继续观测
- **WHEN** fixture temp run 被创建并记录
- **THEN** runs 列表可以再次进入该 run 的观测页与结果页
- **AND** 客户端依据 `run_source` 选择正确后端链路读取状态、事件和 bundle
