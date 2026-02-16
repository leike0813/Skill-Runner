## 1. API 契约

- [ ] 1.1 新增 `GET /v1/jobs/{request_id}/events` SSE 端点
- [ ] 1.2 新增 `GET /v1/temp-skill-runs/{request_id}/events` SSE 端点
- [ ] 1.3 定义统一事件类型：`snapshot/stdout/stderr/status/heartbeat/end`
- [ ] 1.4 为事件流增加 offset 入参：`stdout_from`、`stderr_from`

## 2. 服务实现

- [ ] 2.1 在 `run_observability` 抽象增量读取能力（按 offset 读取 stdout/stderr）
- [ ] 2.2 复用现有状态读取逻辑，推送 `status` 变化事件
- [ ] 2.3 实现 heartbeat 与 chunk 限流（避免超大单帧）
- [ ] 2.4 实现 `waiting_user` 的 `end(reason=waiting_user)` 关闭语义
- [ ] 2.5 实现终态 `end(reason=terminal)` 关闭语义

## 3. 兼容与边界

- [ ] 3.1 保持 `GET /logs` 现有返回格式不变
- [ ] 3.2 保持 UI `/ui/runs/{request_id}/logs/tail` 现有行为不变
- [ ] 3.3 处理请求不存在、run 未创建、路径不可读等错误场景

## 4. 测试

- [ ] 4.1 单测：SSE 首帧返回 snapshot
- [ ] 4.2 单测：stdout/stderr 追加时发出增量事件且 offset 单调递增
- [ ] 4.3 单测：重连携带 offset 后不重复推送
- [ ] 4.4 单测：waiting_user 触发 `status + end(waiting_user)` 并关闭连接
- [ ] 4.5 单测：终态触发 `status + end(terminal)` 并关闭连接
- [ ] 4.6 集成：interactive 流程中 pending/reply 前后可分别建立事件流并拿到连续日志

## 5. 文档

- [ ] 5.1 更新 `docs/api_reference.md`：新增 SSE 端点、事件格式、重连示例
- [ ] 5.2 更新 `docs/dev_guide.md`：说明 SSE 与全量 `/logs` 的定位差异
