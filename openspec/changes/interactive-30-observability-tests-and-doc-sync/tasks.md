## 0. 前置检查

- [ ] 0.1 `interactive-25-api-sse-log-streaming` 已完成并可用
- [ ] 0.2 `interactive-27-unified-management-api-surface` 已完成并可用
- [ ] 0.3 `interactive-28-web-client-management-api-migration` 已完成并可用
- [ ] 0.4 `interactive-29-decision-policy-and-auto-continue-switch` 已完成并可用
- [ ] 0.5 `interactive-26-job-termination-api-and-frontend-control` 已完成并可用

## 1. 可观测语义

- [ ] 1.1 更新 run 状态响应，补充 pending interaction 相关字段
- [ ] 1.2 调整 `run_observability` 的日志轮询建议（waiting_user -> poll=false）
- [ ] 1.3 回归现有运行状态列表与详情接口

## 2. 测试矩阵

- [ ] 2.1 单测：waiting_user 状态可被正确读取与展示
- [ ] 2.2 单测：logs tail 在 waiting_user 下返回 `poll=false`
- [ ] 2.3 集成：交互回合成功/失败/冲突分支
- [ ] 2.4 e2e：客户端按 pending/reply 流程推进到终态
- [ ] 2.5 集成：cancel 后可观测状态与事件语义一致（含 `canceled`）

## 3. 文档

- [ ] 3.1 更新 `docs/api_reference.md` 的交互模式章节与示例
- [ ] 3.2 更新 `docs/dev_guide.md`，说明 non-interactive 约束改为“按 execution_mode 生效”
- [ ] 3.3 增加“外部优先 API、内建 UI 同步遵循统一契约”的边界说明
