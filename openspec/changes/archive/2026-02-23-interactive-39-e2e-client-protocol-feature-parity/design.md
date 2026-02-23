## Context

最新运行时协议已经在后端和管理 UI 中形成稳定能力集合：
- `run_event`（RASP）+ `chat_event`（FCMP）双层事件
- `cursor` 续传
- 历史区间拉取（`events/history`）
- `raw_ref` 到日志字节区间回跳（`logs/range`）
- 低置信度诊断与事件关联视图

在最近变更后，E2E 客户端已落地以下基线能力：
- source-aware 双链路映射（installed→`/v1/jobs/*`，temp→`/v1/temp-skill-runs/*`）
- `events/history` 与 `logs/range` 代理
- fixture skill（`tests/fixtures/skills`）动态打包并走临时 skill 执行链路

当前 change 仍未落地的部分，主要集中在观测 UI 增强与录制摘要增强。

## Baseline vs Delta

**Baseline（已完成）**
- 代理层路由矩阵与 source-aware 同构能力面（pending/reply/history/range）。
- fixture temp-skill 入口、动态打包上传、`run_source` 贯通到 runs/result/recording。
- 基础集成测试覆盖 installed/temp 双链路关键代理能力。

**Delta（本 change 待实现）**
- `run_observe.html` 增加 relation 视图、`raw_ref` 回跳预览、low-confidence 标识。
- 断线重连后的“cursor + history”协同补偿策略。
- 录制模型新增协议定位摘要字段（`cursor`/关键事件/`raw_ref` 摘要）及回放展示。
- 对应测试与文档的最终一致性收敛。

## Goals / Non-Goals

**Goals:**
- 让 E2E 客户端 Run 观测页达到与管理 UI 同级别的协议消费能力。
- 增加 e2e 代理 API：`events/history` 与 `logs/range`。
- 在 UI 中增加 relation 视图、`raw_ref` 回跳和低置信度标识。
- 让录制回放包含协议关键定位信息，支持排障重现。
- 支持 fixture skill 动态打包上传并走 `/v1/temp-skill-runs` 两步执行链路。
- 支持同一客户端按 run source（installed/temp）读取状态、事件、结果与 bundle。

**Non-Goals:**
- 不替换 E2E 客户端技术栈。
- 不改变后端协议本身（本 change 仅消费既有协议能力）。
- 不引入新的后端存储模型。

## Decisions

### Decision 1: E2E 观测页继续采用 FCMP-first，RASP 用于辅助可视化
主对话区仅渲染 `chat_event` 的稳定对话语义；`run_event` 主要用于：
- 低置信度读取（`source.confidence`）
- 事件关联视图（`correlation`）
- `raw_ref` 证据定位

### Decision 2: 历史补偿通过代理 API 暴露，不直接跨域调用后端
新增 e2e 客户端代理端点：
- `GET /api/runs/{request_id}/events/history`
- `GET /api/runs/{request_id}/logs/range`

由 `e2e_client/backend.py` 统一后端请求，采用 source-aware 映射矩阵：
- `run_source=installed` → `/v1/jobs/{request_id}/*`
- `run_source=temp` → `/v1/temp-skill-runs/{request_id}/*`

不再将 `/v1/management/runs/*` 作为 run 读/交互路径。

### Decision 3: raw_ref 回跳与关系视图复用管理 UI 的信息组织方式
E2E 观测页新增：
- 事件关系窗口：按 `seq/type/session` 展示可点击节点
- raw_ref 预览窗口：点击后请求 `logs/range` 并显示字节区间内容

以“轻量同构”方式实现，不要求像管理 UI 一样完全一致的样式。

### Decision 4: 低置信度仅做展示，不影响事件消费流程
当 `confidence < 0.7` 时在对话条目显示 low-confidence 标识；  
不改变原始事件流，不引入额外过滤逻辑。

### Decision 5: 录制模型补充协议定位字段
在保留现有 `create/upload/reply/result_read` 基础上，补充可选记录：
- 关键 `chat_event` 摘要
- 最近 `cursor`
- `raw_ref` 引用摘要（若存在）

用于回放时快速定位上下文。

### Decision 6: fixture skill 使用独立 run source，并在运行时打包上传
新增 fixture 执行入口：
- 从 `tests/fixtures/skills/<fixture_skill_id>` 读取 `runner.json` 与 schemas 渲染运行表单；
- 提交时先调用 `POST /v1/temp-skill-runs`；
- 然后将 fixture skill 目录运行时动态打包为 zip，调用 `POST /v1/temp-skill-runs/{request_id}/upload`（可附带输入 zip）。

客户端在 recording 中记录 `run_source=temp`，后续观测/结果页按 source 走对应 API 路由。

### Decision 7: pending/reply/history/range 在 installed 与 temp 上保持同构
E2E 客户端代理层必须按 source 提供同构能力面：
- pending/reply
- events/history
- logs/range

两链路仅路径不同，不允许语义分叉或“某链路不可用”的兜底降级。

## Risks / Trade-offs

- [风险] 前端状态机会更复杂（实时 + 历史 + 关系视图）  
  → Mitigation: 保持 FCMP-first 主路径，历史/回跳作为可选辅助区。

- [风险] 日志区间请求过大影响页面性能  
  → Mitigation: 限制默认请求窗口，按需加载。

- [风险] 录制文件体积增长  
  → Mitigation: 仅记录摘要，不落完整事件流。

## Migration Plan

1. 更新 `builtin-e2e-example-client` delta spec 与 tasks，明确“已完成基线”和“剩余增量”边界。
2. 在 `run_observe.html` 实现 relation/raw_ref/low-confidence UI，并保持 FCMP-first 主路径。
3. 在观测页加入 cursor/history 协同补偿逻辑，确保断线重连可恢复。
4. 扩展 `e2e_client/recording.py` 与回放展示，新增协议定位摘要字段且保持文件体积可控。
5. 补齐观测增强对应测试，并更新 `docs/e2e_example_client_ui_reference.md` 使其与实现一致。
