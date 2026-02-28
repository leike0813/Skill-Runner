# 文档一致性检查与汇总报告（2026-02-16）

## 检查范围
- 本轮改动相关契约：
  - `GET /v1/jobs/{request_id}`
  - `POST /v1/jobs/{request_id}/interaction/reply`
  - `GET /v1/management/runs/{request_id}`
  - `GET /v1/temp-skill-runs/{request_id}`
- 本轮改动相关文档：
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
  - `openspec/specs/interactive-run-restart-recovery/spec.md`
  - `openspec/specs/interactive-orphan-process-reconciliation/spec.md`

## 对照基线（Source of Truth）
- 代码与模型：
  - `server/models.py`
  - `server/routers/jobs.py`
  - `server/routers/management.py`
  - `server/routers/temp_skill_runs.py`
  - `server/services/run_store.py`
  - `server/services/run_observability.py`
- 规格：
  - `openspec/specs/interactive-run-restart-recovery/spec.md`
  - `openspec/specs/interactive-orphan-process-reconciliation/spec.md`

## 检查结果
1. `RequestStatusResponse` 恢复字段与文档一致：
   - `recovery_state/recovered_at/recovery_reason` 已在模型与 jobs/temp 接口对齐。
2. `management/runs` 恢复字段与文档一致：
   - `ManagementRunConversationState` 包含恢复字段，文档已补齐字段清单。
3. `interaction/reply` 返回状态语义原有偏差已修复：
   - 实现中 `status` 可能为 `queued` 或 `running`（sticky_process），文档已补充分支说明。
4. OpenSpec 归档后主 spec 文案完整性已修复：
   - 两份主 spec 的 `Purpose` 从 `TBD` 更新为明确语义描述。

## 本次修正项
1. `docs/api_reference.md`
   - 在 `InteractionReplyResponse` 下补充 `status=queued|running` 的分支语义说明。
2. `docs/dev_guide.md`
   - 在 management API 字段说明补充 `recovery_state/recovered_at/recovery_reason`。
3. `openspec/specs/interactive-run-restart-recovery/spec.md`
   - 将 `Purpose` 从 `TBD` 更新为重启恢复/状态收敛目标说明。
4. `openspec/specs/interactive-orphan-process-reconciliation/spec.md`
   - 将 `Purpose` 从 `TBD` 更新为孤儿与失效绑定对账目标说明。

## 风险与说明
- 当前仓库处于大规模未提交状态，本报告仅覆盖“本轮改动相关接口与文档”。
- 未发现会导致接口消费者误用的剩余文档冲突项。

## 结论
- 本轮文档一致性检查通过。
- 已完成汇总报告与必要修正文档同步，可作为本轮改动的交付记录。
