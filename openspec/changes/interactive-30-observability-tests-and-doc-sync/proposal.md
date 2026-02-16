## Why

交互能力上线后，调用方和运维方需要明确知道 run 当前是“正在执行”还是“等待用户输入”。  
如果可观测与测试体系不跟进，容易出现：

1. 轮询逻辑误把 `waiting_user` 当作终态或失败。
2. 监控侧持续拉取日志，造成无效负载。
3. 文档与真实行为不一致，接入方无法正确实现客户端流程。

## Dependency

- 本 change 依赖 `interactive-25-api-sse-log-streaming` 提供事件流接口契约。
- 本 change 依赖 `interactive-27-unified-management-api-surface` 提供统一管理 API 分层与字段语义。
- 本 change 依赖 `interactive-28-web-client-management-api-migration` 完成内建客户端对统一接口的迁移。
- 本 change 依赖 `interactive-26-job-termination-api-and-frontend-control` 提供 cancel 终态语义。
- 本 change 依赖 `interactive-29-decision-policy-and-auto-continue-switch` 提供决策协议与 strict 开关行为语义。
- `interactive-30` 负责在上述契约基础上补齐状态语义、测试矩阵与文档收口。

## What Changes

1. 更新状态与日志可观测语义：
   - 明确 `waiting_user` 为非终态；
   - `logs/tail` 在 `waiting_user` 下 `poll=false`（无活动子进程）。

2. 增加交互可观测字段：
   - 状态查询返回 `pending_interaction_id`（如有）；
   - `interaction/pending` 返回交互摘要，供 API 客户端展示。

3. 测试矩阵扩展：
   - 单测覆盖 waiting_user 与 resume；
   - 集成测试覆盖“多次问答后成功/失败”路径；
   - 回归 auto 路径不变。

4. 文档同步：
   - API 参考新增交互模式章节与时序图；
   - 明确“外部客户端优先使用 API 契约，内建 UI 同步遵循同一契约”。

## Impact

- `server/services/run_observability.py`
- `server/routers/jobs.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_run_observability.py`
- `tests/unit/test_v1_routes.py`
- `tests/integration/run_integration_tests.py`
- `tests/e2e/run_e2e_tests.py`
