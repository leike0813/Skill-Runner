# Design: Complete Runtime File Contract Cutover And Scan

## 1. Canonical Run File Contract

### 1.1 Allowed Files

新 run 只允许以下 canonical 文件：

- `.state/state.json`
- `.state/dispatch.json`
- `.audit/request_input.json`
- `.audit/meta.<attempt>.json`
- `.audit/orchestrator_events.<attempt>.jsonl`
- `.audit/events.<attempt>.jsonl`
- `.audit/fcmp_events.<attempt>.jsonl`
- `.audit/stdin.<attempt>.log`
- `.audit/stdout.<attempt>.log`
- `.audit/stderr.<attempt>.log`
- `.audit/pty-output.<attempt>.log`
- `.audit/fs-before.<attempt>.json`
- `.audit/fs-after.<attempt>.json`
- `.audit/fs-diff.<attempt>.json`
- `.audit/parser_diagnostics.<attempt>.jsonl`
- `.audit/protocol_metrics.<attempt>.json`
- `result/result.json`
- `artifacts/*`
- `bundle/*`
- `uploads/*`
- `.<engine>/skills/<skill_id>/...`

### 1.2 Forbidden Files

新 run 明确禁止生成：

- `status.json`
- `current/projection.json`
- `interactions/`
- `interactions/pending.json`
- `interactions/pending_auth.json`
- `interactions/pending_auth_method_selection.json`
- `interactions/history.jsonl`
- `interactions/runtime_state.json`
- `logs/`
- `logs/stdout.txt`
- `logs/stderr.txt`
- `raw/`
- `raw/output.json`
- 根目录 `input.json`

## 2. Truth Layers

### 2.1 Current Truth

唯一 current truth:

- `.state/state.json`

### 2.2 Dispatch Truth

唯一 dispatch truth:

- `.state/dispatch.json`

### 2.3 Terminal Truth

唯一 terminal truth:

- `result/result.json`

### 2.4 Audit Truth

`.audit/*` 为 attempt-scoped history-only files。

parser diagnostics 和 protocol metrics 只承担诊断，不具备状态权威。

## 3. Read Priority

所有新 run 的读取路径必须遵循：

1. `.state/state.json`
2. `.state/dispatch.json`
3. `.audit/*`
4. `result/result.json`

明确禁止：

- 对新 run 从 `status.json` fallback
- 对新 run 从 `current/projection.json` fallback
- 对新 run 从 `interactions/*` fallback
- 从 `result/result.json` 推断 waiting/running/queued

## 4. Create-Run Skeleton

`WorkspaceManager.create_run()` 只允许创建：

- `.state/`
- `.audit/`
- `result/`
- `artifacts/`
- `bundle/`
- `uploads/`

不再创建：

- `interactions/`
- `logs/`
- `raw/`

## 5. Request Snapshot

request 输入快照统一迁移到：

- `.audit/request_input.json`

规则：

- 仅用于审计、回放、bundle
- runtime 核心执行路径不得依赖 run 根目录 `input.json`
- 新 run 禁止写根目录 `input.json`

## 6. Temp Skill and Run-Local Skill

普通 skill 与 temp skill 都采用 run-local snapshot 模型：

- create-run 时 materialize 到 run-local snapshot
- resumed attempt 只从 run-local snapshot 恢复
- temp skill 上传包直接解包到 run-local snapshot
- temp staging 不再作为运行期文件协议的一部分
- 上传 zip 不再作为持久运行资产保留

## 7. Data Reset

reset 后必须：

- 删除所有运行时 DB
- 删除 `data/runs`
- 删除 `data/requests`
- 删除 `data/temp_skill_runs`
- 删除 `data/skill_installs`
- 按配置选择是否删除 logs / engine auth sessions / agent status / ui_shell_sessions

reset 后只能重建新的 canonical 目录骨架，不得重建 legacy run 结构。

## 8. Guardrails

新增自动扫描测试，阻止生产代码和关键测试夹具重新引入以下路径：

- `status.json`
- `current/projection.json`
- `interactions/*`
- `logs/stdout.txt`
- `logs/stderr.txt`
- `raw/output.json`
- 根目录 `input.json`
