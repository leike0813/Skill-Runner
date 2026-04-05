## Context

Qwen Code 的 stream parser 当前状态（`stream_parser.py` 第 126 行）：

```python
def start_live_session(self) -> LiveStreamParserSession:
    raise NotImplementedError("Qwen live stream parser is not implemented yet")
```

`parse_runtime_stream` 方法也尚未实现。这意味着 Qwen engine 无法支持：
- 运行时流式事件输出（`/v1/jobs/{id}/events`）
- 实时聊天冒泡投影（`/v1/jobs/{id}/chat`）
- 会话中鉴权信号检测（`auth_signal`）

真实集成又补充暴露出两个配套问题：
- 即便 parser 已经识别到 `qwen_oauth_waiting_authorization`，provider-aware 的 `qwen` 如果请求侧缺失 `provider_id`，仍会在 `waiting_auth` 编排中失败；
- E2E 示例前端此前仍有部分路径沿用旧的 `provider/model` 提交习惯，没有完全满足 `artifacts/frontend_upgrade_guide_2026-04-04.md`。

## Design Decisions

### 1. 参考 Opencode 模式

Opencode 的 stream parser 实现相对清晰，适合作为 Qwen 的参考模板：
- NDJSON 流解析结构清晰
- `turn_start` / `turn_complete` marker 提取逻辑简洁
- `LiveSession` 实现适中，不过于复杂（如 Claude）也不过于简化（如 Gemini）

### 2. 语义对齐优先

这轮实现不再停留在“只要能出聊天文本”的最小版本，而是直接对齐现有引擎的通用语义面：
- **必须支持**: `assistant_messages`、`process_events`、`turn_markers`、`run_handle`、`auth_signal`
- **语义约束**:
  - `thinking -> reasoning`
  - `run_shell_command -> command_execution`
  - 其余 qwen 工具默认 `tool_call`
  - 普通 `text` 只做 `assistant_message`
- **诊断信息**: 基础 diagnostic codes（如 `PTY_FALLBACK_USED`、`UNPARSED_CONTENT_FELL_BACK_TO_RAW`）

### 3. Qwen NDJSON 事件类型

根据现有 `parse` 方法和 CLI `--output-format stream-json` 输出，支持以下事件类型：

| 事件类型 | 来源 | 用途 |
|----------|------|------|
| `system` + `subtype=init` | stdout | 提取 `session_id` 作为 `run_handle`，并作为 turn start 首选锚点 |
| `assistant.message.content[].type=thinking` | stdout | 提取为 `process_event(reasoning)` |
| `assistant.message.content[].type=tool_use` | stdout | 提取为 `process_event(tool_call/command_execution)` |
| `assistant.message.content[].type=text` | stdout | 提取为 `assistant_message` |
| `user.message.content[].type=tool_result` | stdout | 提取为 `process_event(tool_call/command_execution)` |
| `result` | stdout | 标记 `turn_complete`，提取 `usage/result_subtype`，并给出最终 assistant 文本候选 |

### 4. 认证信号检测复用

通过 `parser_auth_patterns` 配置复用通用检测逻辑：
- `qwen_oauth_token_expired` - OAuth token 过期检测
- `qwen_api_key_missing` - API key 缺失检测
- `qwen_oauth_waiting_authorization` - OAuth device flow 等待授权横幅检测

Qwen 的关键现实约束是：结构化 NDJSON 语义来自 `stdout`，但 OAuth device flow waiting banner 是普通 `stderr` 文本。设计上应明确：
- `start_live_session()` 继续只负责 `stdout/pty` 的 NDJSON 语义；
- `parse_runtime_stream(stdout/stderr/pty)` 负责综合文本证据并返回 `auth_signal`；
- `waiting_auth` 进入由标准 lifecycle 消费 `EngineRunResult.auth_signal_snapshot` 驱动，而不是依赖额外的 live diagnostic 事件。

### 5. 继承 NdjsonLiveStreamParserSession

使用基类提供的：
- NDJSON 行缓冲区（带溢出保护）
- 行修复逻辑（truncated JSON repair）
- 诊断 emission 生成

### 6. parser 信号到 waiting_auth 的 provider-aware handoff

Qwen 是 provider-aware engine，因此 parser 产出 `auth_signal` 之后，还必须能在标准编排路径里落到具体 provider。

设计约束：
- 标准路径仍然是前端显式提交 `provider_id`；
- 但当请求侧遗漏 `provider_id`，且 auth signal 已通过 `matched_rule_ids` 明确指向单一 qwen provider 时，auth orchestration 可以做窄范围 fallback；
- 当前只允许：`qwen_oauth_waiting_authorization -> qwen-oauth`；
- 该 fallback 放在 auth orchestration 层，而不是要求 parser 输出额外的非标准 provider 推导字段。

### 7. E2E 示例前端的 provider-aware 对齐

为了让这次 parser / waiting_auth 修复在真实入口上可落地，E2E client 也要同步满足升级指引：
- 创建 run 时正式传递 `provider_id`；
- `model` 只表达模型本身，不再默认把 provider 重新编码回 `model`；
- run form 的 provider/model 选择优先读取 engine catalog 里的 `provider_id` 与 `model` 字段；
- `run_observe` 继续沿用已经切换后的 `auth_code_or_url`、`accepts_chat_input`、`input_kind` 语义。

## Implementation

### parse_runtime_stream 方法结构

```python
def parse_runtime_stream(
    self,
    *,
    stdout_raw: bytes,
    stderr_raw: bytes,
    pty_raw: bytes = b"",
) -> RuntimeStreamParseResult:
    # 1. 使用 strip_runtime_script_envelope + stream_lines_with_offsets 处理原始输出
    # 2. 使用 collect_json_parse_errors 收集 NDJSON 记录
    # 3. 遍历记录提取 session_id, run_handle, assistant_messages, process_events, turn_markers
    # 4. 调用 detect_auth_signal_from_patterns 检测鉴权信号
    # 5. 返回 RuntimeStreamParseResult
    #
    # provider-aware fallback 不在 parser 内部完成；
    # 当 matched_pattern_id == "qwen_oauth_waiting_authorization" 且请求未提供 provider_id 时，
    # 上层 auth orchestration 在消费 auth_signal_snapshot 时将 provider 规范化为 "qwen-oauth"。
```

### _QwenLiveSession 类结构

```python
class _QwenLiveSession(NdjsonLiveStreamParserSession):
    def __init__(self, parser: QwenStreamParser) -> None:
        super().__init__(accepted_streams={"stdout", "pty"})
        self._parser = parser
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._run_handle_emitted = False
    
    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        # 处理 NDJSON payload，发出 run_handle / process_event / assistant_message / turn_marker
```

### 导入依赖

```python
from server.runtime.adapter.common.live_stream_parser_common import NdjsonLiveStreamParserSession
from server.runtime.adapter.common.parser_auth_signal_matcher import detect_auth_signal_from_patterns
from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
    RuntimeStreamRawRef,
    RuntimeTurnMarker,
)
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
```

## Failure Handling

1. **NDJSON 解析失败** - 回退到原始文本，记录 `UNPARSED_CONTENT_FELL_BACK_TO_RAW` diagnostic
2. **PTY 回退** - 当 stdout 无有效内容时使用 pty 输出，记录 `PTY_FALLBACK_USED`
3. **行溢出** - 使用基线的 overflow 修复逻辑，记录 `RUNTIME_STREAM_LINE_OVERFLOW_REPAIRED` 或 `UNREPAIRABLE`
4. **鉴权失败** - 通过 `auth_signal` 返回，由上层 auth orchestration 和 lifecycle 处理

## Integration Notes

- parser 层不负责猜测 provider，只负责给出标准 `auth_signal`
- auth orchestration 层负责在 qwen 的明确 waiting banner 上做窄范围 provider fallback
- E2E 示例前端负责把 `provider_id + model` 作为默认提交方式，从源头避免 qwen `waiting_auth` 因 provider 缺失失败

## Future Work

- `stream_event` 增量更新语义
- 更细粒度的 diagnostic codes
