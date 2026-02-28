## Architecture Intent

本次为“硬切换 + UI 收口”变更，目标是让 runtime options 语义与真实运行行为一一对应，避免历史兼容键继续泄漏到接口和前端。

## Runtime Option Contract (Hard Cut)

### Allowed Runtime Option Keys

- `execution_mode` (`auto` | `interactive`)
- `no_cache` (bool)
- `debug` (bool)
- `debug_keep_temp` (bool)
- `interactive_auto_reply` (bool, default `false`)
- `interactive_reply_timeout_sec` (positive int)

### Removed Keys (422)

- `verbose`
- `session_timeout_sec`
- `interactive_wait_timeout_sec`
- `hard_wait_timeout_sec`
- `wait_timeout_sec`
- `interactive_require_user_reply`

## Semantic Mapping

### Interactive Auto Reply

- 新语义：`interactive_auto_reply=true` 时，`waiting_user` 超时后由后台自动提交回复并续跑。
- `interactive_auto_reply=false` 时，严格等待用户回复，不进行超时自动回复。
- 默认值：`false`。

### Interactive Reply Timeout

- 统一使用 `interactive_reply_timeout_sec`。
- 仅用于 interactive waiting 超时调度窗口。
- 在 `interactive_auto_reply=false` 时可保留记录，但不会触发 auto-decide。

## E2E UI Behavior

### Visibility Rules

1. `debug_keep_temp` 仅在 `run_source=temp` 显示。
2. `interactive_auto_reply` 与 `interactive_reply_timeout_sec` 仅在 `execution_mode=interactive` 显示。
3. `interactive_reply_timeout_sec` 仅在 `interactive_auto_reply=true` 时显示。

### Control Type Rules

- `interactive_auto_reply` 使用 checkbox（布尔），不再使用 dropdown。

### Labels (Chinese)

- `no_cache`：禁用缓存机制
- `debug`：Debug模式
- `debug_keep_temp`：保留上传的临时 Skill 包（Debug用）
- `interactive_auto_reply`：超时自动回复
- `interactive_reply_timeout_sec`：回复超时阈值

## Compatibility Strategy

本变更采用硬切换，不保留旧键自动映射；调用方须按新键提交。

受影响面：

- API 客户端
- E2E 示例客户端
- integration/e2e 测试输入
- 文档示例 payload

## Risks and Mitigations

1. **旧客户端立即报错**
   - 通过文档与 E2E 示例同步更新，明确 422 错误文案。
2. **交互超时配置误用**
   - 仅保留单一 timeout 键，减少歧义。
3. **前端显示误导**
   - 通过 execution_mode/run_source 条件渲染收口。
