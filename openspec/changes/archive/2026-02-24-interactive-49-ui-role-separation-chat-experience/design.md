## Overview

本变更将 UI 切分为两条明确职责链：

1. 管理 UI：审计优先，显示 FCMP/RASP/orchestrator 历史与 raw 输出；不支持 reply。
2. E2E UI：对话优先，仅展示对话与基础状态；不展示技术诊断面板。

## Decision 1: 管理 API 增加 protocol history 读取面

新增 `GET /v1/management/runs/{request_id}/protocol/history`：

- `stream=fcmp|rasp|orchestrator`
- `attempt`（默认最新轮次）
- 过滤参数：`from_seq`, `to_seq`, `from_ts`, `to_ts`
- 返回：`{request_id, stream, attempt, available_attempts, count, events}`

实现侧复用 `run_observability` 审计文件读取能力，统一序列过滤逻辑。

同时增强 `GET /v1/management/runs/{request_id}/logs/range`：

- 新增 `attempt` 参数（默认最新）
- raw_ref 回跳按对应轮次读取 `.audit/stdout.{attempt}.log` / `.audit/stderr.{attempt}.log` / `.audit/pty-output.{attempt}.log`

## Decision 2: 管理 UI 仅保留观测与运维动作

`run_detail.html` 删除 pending/reply 表单及调用路径，保留：

1. 对话区（FCMP）
2. raw stderr
3. FCMP/RASP/orchestrator 审计视图
4. raw_ref 片段预览
5. cancel 动作
6. attempt 左右翻页控件（FCMP/RASP/orchestrator/raw stderr 同步按轮次切换）

页面重进后先加载历史再接实时流，确保历史对话与审计信息可见。

## Decision 3: E2E 对话语义修正

`run_observe.html` 采用对话产品形态：

1. Agent 气泡左侧，User 气泡右侧。
2. `Ctrl+Enter`/`Cmd+Enter` 发送回复。
3. `assistant.message.final` 中 Ask User YAML：
   - 提取 `<ASK_USER_YAML>` 或 fenced `ask_user_yaml`
   - 解析为提示卡（interaction_id/kind/prompt/options/required_fields）
   - YAML 原文不进入聊天气泡
4. `user.input.required` 归类为 Agent 问询，并与提示卡按 `interaction_id + prompt` 去重。
5. 终态后若 `has_result || has_artifacts`，追加 Agent 最终摘要气泡。
6. 保留折叠文件树能力（默认收起，终态展开时加载）。

## Decision 4: E2E 内部 final-summary API

新增 `GET /api/runs/{request_id}/final-summary`，聚合 result 与 artifacts：

- `has_result`: bool
- `has_artifacts`: bool
- `artifacts`: list
- `result_preview`: 文本化预览（截断）

该接口失败时前端静默降级，不影响主对话流程。

## Decision 5: FCMP 历史游标与去重语义

1. `/events` 与 `/events/history` 对外 `chat_event.seq` 统一为跨 attempt 全局单调递增，用于 cursor 续传。
2. `fcmp_events.{attempt}.jsonl` 落盘时同步写全局 `seq`；attempt 内原始序号保留为 `meta.local_seq`，不影响管理侧 protocol history 的按轮次审计。
3. 在 waiting_user 场景中，`assistant.message.final` 与 `user.input.required` 若同义问询，后者 prompt 退化为控制提示，避免重复正文。
4. `interaction.reply.accepted` 仅发“当前 attempt 对应回复”，并附 `response_preview` 供 UI 回放用户气泡。
5. 续跑 attempt 中，`interaction.reply.accepted` 必须先于该轮 `assistant.message.final`，避免回放顺序反转。

## Decision 6: orchestrator 事件序列化

1. 新写入 orchestrator 事件包含 attempt 内 `seq`（递增）。
2. 旧 run 若缺失 `seq`，由读侧按文件顺序回填后再过滤与展示。

## Decision 7: E2E 结果页收敛

1. `/runs/{request_id}/result` 路由下线。
2. 文件树/预览能力并入 Observation 页面，采用固定双栏布局避免长文本撑破。
3. 终态摘要采用重试拉取 `final-summary`，降低终态竞态导致的摘要缺失。
4. `conversation.completed` 在 E2E 不再显示文本气泡；终态仅保留 summary 输出。
5. 若 `assistant.message.final` 为结构化 done JSON（`__SKILL_DONE__=true`），E2E 抑制该原始气泡避免双显示。

## Risks & Mitigations

1. 风险：管理端用户误以为不能处理 waiting_user。
   - 缓解：管理页明确定位审计/排障；交互回复留给 E2E/外部客户端。

2. 风险：Ask User YAML 非标准格式导致提示卡解析失败。
   - 缓解：解析失败时仅保留普通 assistant 文本，不阻断后续 `user.input.required` 驱动。

3. 风险：终态摘要重复插入。
   - 缓解：前端使用单次加载守卫，确保每个 run 只追加一次 summary。

4. 风险：多轮审计再次被覆盖。
   - 缓解：协议文件、orchestrator 文件统一改为 `*.{attempt}.jsonl` / `*.{attempt}.json` 分片，不再写聚合文件。

5. 风险：FS diff 被内部目录污染。
   - 缓解：server 与 harness 同步忽略 `.audit/`、`interactions/`、`.codex/`、`.gemini/`、`.iflow/`。
