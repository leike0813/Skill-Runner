## 1. 启动期恢复流程

- [ ] 1.1 新增启动期 `recover_incomplete_runs_on_startup` 流程
- [ ] 1.2 扫描并识别非终态 run（`queued/running/waiting_user`）
- [ ] 1.3 按 `interactive_profile` 应用恢复矩阵并写回状态

## 2. 状态收敛规则

- [ ] 2.1 `waiting_user + resumable`：校验句柄后保持 waiting 或失败
- [ ] 2.2 `waiting_user + sticky_process`：重启后统一标记 `INTERACTION_PROCESS_LOST`
- [ ] 2.3 `queued/running` 无恢复点：标记 `ORCHESTRATOR_RESTART_INTERRUPTED`

## 3. 孤儿进程与资源对账

- [ ] 3.1 增加孤儿进程识别与终止逻辑（幂等）
- [ ] 3.2 清理 stale trust/session 绑定
- [ ] 3.3 校正并发槽位占用状态，避免“幽灵占用”

## 4. 可观测与接口

- [ ] 4.1 增加 `recovery_state/recovered_at/recovery_reason` 字段
- [ ] 4.2 在状态查询与管理 API 暴露恢复字段
- [ ] 4.3 文档化恢复字段含义与排障建议

## 5. 测试

- [ ] 5.1 单测：resumable waiting_user 重启后保持可回复
- [ ] 5.2 单测：sticky_process waiting_user 重启后失败收敛
- [ ] 5.3 单测：running/queued 重启后失败收敛
- [ ] 5.4 单测：孤儿进程清理幂等
- [ ] 5.5 集成：重启恢复后 reply/cancel 行为可用

## 6. 文档

- [ ] 6.1 更新 `docs/api_reference.md`：重启恢复字段与状态语义
- [ ] 6.2 更新 `docs/dev_guide.md`：启动对账机制与故障恢复策略
