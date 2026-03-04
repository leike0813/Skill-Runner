## Context

`waiting_auth` 闭环中的 callback/code 提交依赖一组 orchestrator audit events 来驱动审计、协议翻译和后续状态推进。当前 `run_auth_orchestration_service.py` 已经把 `auth.input.accepted` 等事件视为 canonical lifecycle 记录，但 `runtime_contract.schema.json`、叙述文档和回归测试没有随之同步，导致实现与 schema 漂移。最新事故中，callback URL 提交路径写出的 `accepted_at` 字段无法通过 schema 校验，直接把用户操作升级成了 `Internal Server Error`。

这类问题不能靠单点放宽 schema 结束，因为 auth orchestrator events 已经形成一组相互关联的 contract：`created -> selected/busy -> input.accepted -> session.completed/session.failed/session.timed_out`。只补一处字段会继续留下同组事件的潜在漂移。

## Goals / Non-Goals

**Goals:**
- 将整组 auth orchestrator event 的字段合同统一收敛到单一 schema SSOT。
- 保证 callback/code 提交路径能稳定写入 `auth.input.accepted`，不再因字段漂移触发 500。
- 让 auth orchestrator event 的实现、文档和测试都复用同一 payload 约定，减少重复定义。
- 保持 schema 严格校验，不通过“关闭校验”来掩盖协议漂移。

**Non-Goals:**
- 不改变 auth method selection、auth completion、resume ticket 的业务状态机。
- 不在本 change 中引入新的 auth event 类型。
- 不重做 FCMP ordering 或 waiting_auth UX。
- 不放宽读取路径的脏数据兼容策略以吞掉新的写入错误。

## Decisions

### 1. 以当前 canonical 实现为基线，对齐整组 auth orchestrator event schema

选择依据：
- 真实的 submit/complete/fail 路径已经在生产代码里运行，schema 应首先覆盖 canonical write-path。
- 单点只补 `auth.input.accepted.accepted_at` 无法防止同组其他 event 再次漂移。

实施方式：
- 审计 `auth.session.created`、`auth.method.selected`、`auth.session.busy`、`auth.input.accepted`、`auth.session.completed`、`auth.session.failed`、`auth.session.timed_out` 的真实 payload。
- 在 `runtime_contract.schema.json` 中为这些事件逐项列出允许字段。
- 保持 `additionalProperties: false`，继续把未来的 drift 暴露出来。

备选方案：
- 只给 `auth.input.accepted` 开口子。放弃原因：范围过窄，无法解决同组事件继续漂移的问题。
- 为 auth orchestrator events 改成弱校验。放弃原因：会让协议问题延迟暴露，破坏 runtime schema SSOT。

### 2. 将 auth event payload 结构统一收敛在 orchestration service 层

选择依据：
- 目前 auth orchestrator event 的字段是在多个调用点分别手拼，最容易出现命名细节不一致。
- 与其让 schema 被动追实现，不如让实现也先统一再对齐 schema。

实施方式：
- 在 `run_auth_orchestration_service.py` 内部复用稳定的 payload 构造模式。
- 对同类时间戳字段使用统一命名，例如 `*_at`。
- `run_audit_service.py` 继续只负责“严格校验 + 落盘”，不承担字段补救。

备选方案：
- 在 `run_audit_service.py` 中对 auth 事件做特殊字段兼容。放弃原因：会把协议漂移隐藏在写入层，继续破坏 DRY。

### 3. 文档和 specs 只描述 contract，不重复实现细节

选择依据：
- 这次 change 的价值在于把 contract 钉死，而不是记录某个函数细节。
- 如果文档复述实现细节过多，后续又会形成第二套漂移源。

实施方式：
- `runtime-event-command-schema` 主 spec 收敛为“auth orchestrator event MUST 被 schema 覆盖且严格校验”。
- `interactive-job-api` 主 spec 仅声明“auth input submit 必须记录 accepted event 并继续 auth 流程”。
- `job-orchestrator-modularization` 主 spec 仅声明“orchestration 必须通过统一 contract 写 auth event”。

## Risks / Trade-offs

- [Risk] 新 schema 可能揭露其他尚未覆盖的 auth event drift。 → Mitigation：为整组 auth events 增加 schema registry 回归，而不是只测一条 submit 路径。
- [Risk] 统一 payload 命名时可能影响现有历史审计读取。 → Mitigation：本 change 只收紧写入合同，不改读取兼容策略；历史文件仍走现有 tolerant read。
- [Risk] integration coverage 不足时，500 可能在其它 auth provider 路径复现。 → Mitigation：至少增加 unit 级 submit 回归，并在可行时补一个 interactive observability 集成场景。

## Migration Plan

1. 更新 proposal 涉及的主 spec 与 schema 文档，明确 auth orchestrator event contract。
2. 修改 `runtime_contract.schema.json`，补全整组 auth events 的字段定义。
3. 在 orchestration service 中统一 auth event payload 生成。
4. 补 schema registry、auth orchestration、integration 回归。
5. 跑 runtime schema/protocol/auth 相关测试和 mypy。

回滚策略：
- 若实现回归，可回滚 orchestration payload 统一和 schema 变更；由于本 change 不新增事件类型，回滚边界清晰。

## Open Questions

- 无新的产品决策问题；字段范围以当前 canonical auth submit/complete/fail 实现为准。
