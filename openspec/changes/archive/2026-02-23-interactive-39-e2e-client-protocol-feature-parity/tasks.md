## 1. Protocol Capability Alignment

- [x] 1.1 在 `builtin-e2e-example-client` 规格中补充 latest protocol 对齐要求（history/raw_ref/relation/low-confidence）
- [x] 1.2 明确 E2E 客户端代理 API 的 source-aware 参数映射约束（installed→jobs，temp→temp-skill-runs）
- [x] 1.3 明确录制回放模型中的协议定位摘要字段约束

## 2. Backend Proxy Integration (E2E Client Side)

- [x] 2.1 在 `e2e_client/backend.py` 增加 `events/history` 调用方法
- [x] 2.2 在 `e2e_client/backend.py` 增加 `logs/range` 调用方法
- [x] 2.3 将 installed source 的 run 读/交互映射统一切换到 `/v1/jobs/*`（不再依赖 `/v1/management/runs/*`）
- [x] 2.4 为 temp source 补齐 `pending/reply/history/range` 代理调用（与 installed 同构）
- [x] 2.5 在 `e2e_client/routes.py` 新增 `GET /api/runs/{request_id}/events/history`
- [x] 2.6 在 `e2e_client/routes.py` 新增 `GET /api/runs/{request_id}/logs/range`
- [x] 2.7 在 `e2e_client/routes.py` 保证 `GET /api/runs/{request_id}/pending` 与 `POST /api/runs/{request_id}/reply` 按 source 双链路可用

## 3. Run Observation UI Upgrade

- [x] 3.1 在 `run_observe.html` 增加结构化事件关联视图
- [x] 3.2 在 `run_observe.html` 增加 `raw_ref` 回跳预览窗口与交互
- [x] 3.3 在 `run_observe.html` 增加 low-confidence 标识展示
- [x] 3.4 保持 FCMP-first 主对话区语义，避免回退到 raw 文本主导
- [x] 3.5 补齐断线重连与历史补偿协同逻辑（cursor + history）

## 4. Recording/Replay Enhancement

- [x] 4.1 扩展录制模型，记录协议定位摘要（cursor/关键事件/raw_ref）
- [x] 4.2 回放页展示新增摘要字段，确保可读性
- [x] 4.3 控制录制体积，避免写入全量事件流

## 5. Tests and Docs

- [x] 5.1 新增/更新 e2e 客户端集成测试：history 代理与 logs/range 代理
- [x] 5.2 新增/更新 source parity 测试：installed/temp 在 pending/reply/history/range 上行为同构
- [x] 5.3 新增/更新观测页测试：raw_ref 回跳、relation 视图、低置信度标识
- [x] 5.4 运行全量单元测试并修复回归
- [x] 5.5 更新 `docs/e2e_example_client_ui_reference.md` 与实现一致（覆盖观测增强与摘要回放）
- [x] 5.6 执行 OpenSpec 校验并确认 change 维持 apply-ready

## 6. Fixture Temp-Skill Execution Path

- [x] 6.1 首页新增 fixture skills 列表，来源 `tests/fixtures/skills`
- [x] 6.2 新增 `/fixtures/{fixture_skill_id}/run` 页面与提交流程
- [x] 6.3 提交时动态打包 fixture skill，并走 `/v1/temp-skill-runs` 两步链路
- [x] 6.4 录制文件补充 `run_source`，并支持 run/result/event/bundle 按 source 路由
- [x] 6.5 新增/更新集成测试覆盖 fixture temp-skill 执行链路
