## 1. API 入口

- [x] 1.1 新增 `POST /v1/jobs/{request_id}/cancel`
- [x] 1.2 新增 `POST /v1/temp-skill-runs/{request_id}/cancel`
- [x] 1.3 统一 `CancelResponse` 返回字段与 HTTP 语义（不存在/幂等/活跃态）

## 2. 编排与进程终止

- [x] 2.1 引入 run 级 `cancel_requested` 控制字段或等价机制
- [x] 2.2 运行中任务可触发 adapter 进程树终止
- [x] 2.3 排队任务在执行关键路径前检查取消标记并短路终止

## 3. 状态写入与收尾

- [x] 3.1 取消后状态统一写入 `RunStatus.CANCELED`
- [x] 3.2 取消后统一写入 `error.code=CANCELED_BY_USER`
- [x] 3.3 取消路径复用收尾：释放并发槽位、清理 trust、更新 run/request store

## 4. 可观测对齐

- [x] 4.1 状态查询可见 `canceled` 终态与错误信息
- [x] 4.2 SSE 终态事件支持 `canceled`
- [x] 4.3 日志保留取消前 stdout/stderr

## 5. 测试

- [x] 5.1 单测：running 状态取消成功并落为 `canceled`
- [x] 5.2 单测：queued 状态取消后不会继续执行
- [x] 5.3 单测：终态重复取消幂等（`accepted=false`）
- [x] 5.4 单测：temp-skill-runs 取消链路
- [x] 5.5 集成：取消后 status/result/logs/SSE 行为一致

## 6. 文档

- [x] 6.1 更新 `docs/api_reference.md`：新增 cancel 接口与响应语义
- [x] 6.2 更新 `docs/dev_guide.md`：取消生命周期与状态机说明
