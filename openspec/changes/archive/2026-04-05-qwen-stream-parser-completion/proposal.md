## Why

在 `add-qwen-code-engine` change 中，Qwen Code 已作为一等公民 engine 接入系统，但其 stream parser 仅实现了基础的 `parse` 方法，缺少 `parse_runtime_stream` 和 `start_live_session` 方法。

这导致以下问题：

1. **无法支持可观测性流式输出** - Qwen engine 无法在管理 UI 上实时显示 run 的聊天冒泡和执行事件；
2. **鉴权信号检测缺失** - 无法在流式输出中实时检测 OAuth token expired 或 API key missing 等鉴权失败；
3. **turn marker 无法生成** - 无法标记 turn start/complete，影响事件流的语义完整性；
4. **engine 能力不一致** - 其他 engine（claude/opencode/gemini）均已支持完整的流式解析，Qwen 作为新 engine 应保持对齐。

### 补充：Qwen OAuth waiting banner 的职责边界

真实 run 表明，Qwen 的 OAuth waiting banner 是普通 `stderr` 文本，而不是 NDJSON live event。  
因此 `waiting_auth` 的正确进入链路应是：

`stderr/stdout/pty -> parse_runtime_stream auth_signal -> adapter auth probe / early-exit -> EngineRunResult.auth_signal_snapshot -> lifecycle/orchestrator -> waiting_auth`

而不是通过额外的 live diagnostic 事件直接驱动 UI。

### 补充：provider-aware handoff 必须可落地

在真实集成中，仅有 parser 检出 `qwen_oauth_waiting_authorization` 还不够。  
如果请求创建时没有显式携带 `provider_id`，`qwen` 作为 provider-aware engine 会在 `waiting_auth` 编排阶段因 `PROVIDER_ID_UNRESOLVED` 失败。

因此这次 change 还需要补齐两项配套：

1. **运行时 provider fallback**  
   当 auth signal 已明确命中 `qwen_oauth_waiting_authorization` 时，后端编排可以将缺失的 provider 规范化为 `qwen-oauth`，从而让 `waiting_auth` 会话真正创建出来。

2. **E2E 示例前端对齐 provider-aware 提交方式**  
   示例前端必须满足 `artifacts/frontend_upgrade_guide_2026-04-04.md` 的要求，创建 run 时正式传递 `provider_id`，并以 `provider_id + model` 作为默认提交语义，而不是继续依赖旧的 `provider/model` 编码。

## What Changes

完成 Qwen engine 的 stream parser 实现，使其支持：

1. **`parse_runtime_stream` 方法** - 解析 Qwen 的真实 NDJSON 流并提取：
   - `session_id` / `run_handle`
   - `assistant_messages`（仅来自 `assistant.message.content[].type=text` 与 `result.result`）
   - `process_events`（`thinking -> reasoning`，`tool_use/tool_result -> tool_call / command_execution`）
   - `turn_markers`（start/complete）
   - `auth_signal`（鉴权信号检测）
   - `diagnostics`（诊断信息）

2. **`_QwenLiveSession` 类** - 实时流解析器，支持：
   - 增量 NDJSON 事件处理
   - `run_handle` / `turn_marker` / `assistant_message` / `process_event` emission

3. **语义对齐** - 与 `codex / claude / opencode` 保持一致：
   - 只有显式 `thinking` 进入 `reasoning`
   - `run_shell_command` 归类为 `command_execution`
   - 其余 qwen tool use/result 默认归类为 `tool_call`
   - 普通 `text` 不再误归类为 `reasoning`

4. **鉴权检测模式增强** - 基于实际 run 观察，添加 OAuth device flow waiting 检测模式，并明确由 `parse_runtime_stream(stdout/stderr/pty)` 负责识别。

5. **waiting_auth handoff 补强** - 当 parser 已给出明确 qwen OAuth waiting 信号时，标准 lifecycle 必须能稳定进入 `waiting_auth`；同时 E2E client 需要按 provider-aware 约定传值，避免真实交互路径仍旧丢失 `provider_id`。

## Scope

### In Scope

- `QwenStreamParser.parse_runtime_stream()` 方法实现
- `_QwenLiveSession` 类实现（继承 `NdjsonLiveStreamParserSession`）
- 导入必要的类型和工具函数
- 类型检查（mypy）通过
- OpenSpec 文档更新
- parser_auth_patterns 配置更新（添加 qwen_oauth_waiting_authorization 规则）
- `waiting_auth` 编排中的 qwen provider fallback
- E2E 示例前端按 `provider_id + model` 提交 qwen / opencode run

### Out of Scope

- `stream_event` 增量更新语义
- MCP 工具调用协议映射
- 新的 Qwen CLI 输出格式支持（仅支持当前 `--output-format stream-json`）

## Impact

主要改动面：

- `server/engines/qwen/adapter/stream_parser.py` - 核心修改
- `tests/unit/test_qwen_adapter.py` / `tests/unit/test_adapter_live_stream_emission.py` - 真实 NDJSON 语义与 final 去重回归
- `server/engines/qwen/adapter/adapter_profile.json` - parser_auth_patterns 配置更新
- `server/engines/qwen/auth/detection.py` - AuthDetector 等待状态检测支持
- `server/services/orchestration/run_auth_orchestration_service.py` - qwen auth signal → provider fallback
- `e2e_client/routes.py` / `e2e_client/templates/run_form.html` - 示例前端 provider-aware 提交对齐
- 类型检查验证
- OpenSpec spec 更新（engine-adapter-runtime-contract）
- qwen waiting_auth 主链路与 live parser 职责边界对齐

测试影响：

- 现有单元测试应继续通过
- 可能需要添加 stream parser 单元测试（可选）
