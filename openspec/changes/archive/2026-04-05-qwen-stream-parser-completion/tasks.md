## Tasks

### Phase 1: 完成 parse_runtime_stream 方法

- [x] 添加必要的类型导入
- [x] 实现 `parse_runtime_stream` 方法主体
  - [x] 处理 stdout/stderr/pty 三路输出
  - [x] 提取 session_id 和 run_handle
- [x] 提取 assistant_messages
- [x] 提取 process_events（reasoning / tool_call / command_execution）
  - [x] 生成 turn_markers（start/complete）
  - [x] 收集 diagnostics
  - [x] 检测 auth_signal
- [x] 返回标准格式的 `RuntimeStreamParseResult`

### Phase 2: 实现 _QwenLiveSession 类

- [x] 定义类继承 `NdjsonLiveStreamParserSession`
- [x] 实现 `__init__` 方法，设置状态跟踪变量
- [x] 实现 `handle_live_row` 方法
  - [x] 处理 `system/subtype=init` → `run_handle` emission
  - [x] 处理 `assistant` → `assistant_message` / `process_event` emission
  - [x] 处理 `user/tool_result` → `process_event` emission
  - [x] 发出 `turn_marker` emissions（start/complete）
- [x] 更新 `start_live_session` 方法返回 `_QwenLiveSession` 实例

### Phase 2.5: 对齐 Qwen 真实语义

- [x] 以真实 run `f4221312-9a02-4f87-b402-97636110dab3` 为基准校准事件类型映射
- [x] `thinking` 只归类为 `reasoning`
- [x] `run_shell_command` 归类为 `command_execution`
- [x] 其他 qwen tools 归类为 `tool_call`
- [x] `assistant text` 不再误归类为 `reasoning`
- [x] final JSON 与 `result.result` 重复时只保留一个 final 候选

### Phase 3: 验证和测试

- [x] 运行类型检查（mypy）
- [x] 检查是否有现有测试需要更新
- [x] 验证 engine_adapter_registry 集成
- [x] 补充 qwen parser 语义分类与 run handle 回归测试
- [x] 补充 qwen live emission / final 去重回归测试

### Phase 4: 文档更新

- [x] 更新 OpenSpec spec（qwen-stream-parser/spec.md）
- [x] 标记 change 为完成

### Phase 5: 对齐 waiting_auth 主链路

- [x] 确认 qwen OAuth waiting banner 通过 `parse_runtime_stream(stdout/stderr/pty)` 产出高置信度 `auth_signal`
- [x] 回退不合规的 live diagnostic 驱动改动，恢复 `auth_signal_snapshot -> lifecycle -> waiting_auth` 主路径
- [x] 更新 proposal/design/spec，明确 live session 只处理 `stdout/pty` NDJSON 语义

### Phase 6: 补齐 provider-aware handoff 与 E2E 真实入口

- [x] 在 auth orchestration 中为 `qwen_oauth_waiting_authorization` 增加窄范围 provider fallback（`qwen-oauth`）
- [x] 更新 qwen 生命周期集成测试，覆盖“auth signal 命中但请求未显式携带 provider_id”仍可进入 `waiting_auth`
- [x] 更新 E2E 示例前端创建 run 的 payload，正式传递 `provider_id`
- [x] 更新 E2E run form 的 provider/model 归一化逻辑，默认使用 `provider_id + model`
- [x] 审计 E2E `run_observe` 是否满足 `frontend_upgrade_guide_2026-04-04.md`

## Dependencies

- 依赖 `add-qwen-code-engine` change 已完成
- 依赖 `generalize-provider-aware-engine-auth` 的共享基础设施

## Definition of Done

1. `QwenStreamParser.parse_runtime_stream()` 返回正确的 `RuntimeStreamParseResult` 格式，并能从 stderr waiting banner 识别高置信度 `auth_signal`
2. `_QwenLiveSession.handle_live_row()` 正确处理 `system/init + assistant + user/tool_result + result` 事件并发射正确的 emission，且不把 stderr banner 误当成 live semantic event
3. 类型检查通过（mypy）
4. 与 `engine_adapter_registry` 集成后，qwen 引擎可以正常执行 run，并通过标准 lifecycle 进入 `waiting_auth`
5. 当 E2E 示例前端用于发起 qwen / opencode run 时，请求 payload 默认符合 provider-aware 约定（`provider_id + model`）
6. qwen 在 FCMP / chat replay 中稳定产出 `assistant.tool_call`、`assistant.command_execution`，且 final 不再重复两份相同 JSON

## Implementation Summary

完成时间：2026-04-04

### 修改文件

1. `server/engines/qwen/adapter/stream_parser.py` - 核心实现
   - 按真实 qwen NDJSON 语义补齐 `process_events`、`run_handle`、`turn_markers`
   - 添加 `_QwenLiveSession` 语义发射与 final 去重
   - 更新 `start_live_session` 返回实际实例

2. `tests/unit/test_qwen_adapter.py` / `tests/unit/test_adapter_live_stream_emission.py` - 真实语义回归
   - 覆盖 `system/init + thinking + tool_use + tool_result + result`
   - 覆盖 qwen live final 去重与 `assistant.tool_call` / `assistant.command_execution`

3. `server/runtime/adapter/base_execution_adapter.py` - Auth probe 逻辑回归到标准 lifecycle 驱动
   - 不再通过额外 live diagnostic 事件驱动 `waiting_auth`

4. `server/services/orchestration/run_auth_orchestration_service.py` - qwen auth signal provider fallback
   - 当命中 `qwen_oauth_waiting_authorization` 且请求未显式提供 provider_id 时，规范化为 `qwen-oauth`

5. `e2e_client/routes.py` / `e2e_client/templates/run_form.html` - 示例前端 provider-aware 对齐
   - 创建 run 的 payload 正式传递 `provider_id`
   - provider/model 选择逻辑优先读取 catalog 中的 `provider_id` 与 `model`

### 测试结果

- mypy 类型检查：通过
- test_adapter_command_profiles.py：12/12 通过
- test_run_auth_orchestration_service.py、test_auth_detection_lifecycle_integration.py：通过
- test_e2e_example_client.py、test_e2e_run_observe_semantics.py：通过
- runtime mandatory regression：109/109 通过
