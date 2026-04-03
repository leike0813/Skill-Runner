# add-claude-code-engine Design

## Architecture

Claude 接入继续沿用现有一等公民 engine 架构：

- 执行侧：`server/engines/claude/adapter/**`
- 鉴权侧：`server/engines/claude/auth/**`
- 配置/模型：`server/engines/claude/config/**`、`models/**`
- 集中注册：engine keys / adapter registry / auth bootstrap / upgrade manager / model registry

## Execution

### Command shape

- start:
  - `claude -p --output-format stream-json --verbose --settings .claude/settings.json <prompt>`
- resume:
  - `claude --resume <session-id> -p --output-format stream-json --verbose --settings .claude/settings.json <prompt>`

`CLAUDE_CONFIG_DIR` 指向 managed agent home 下的 `.claude`，用于读取持久凭据。  
运行期的 session-local settings 由 config composer 写入 `run_dir/.claude/settings.json`，并通过 `--settings` 显式传入，避免污染持久凭据目录。

### Parser strategy

主路径固定使用 `stream-json`。

Claude parser 只抽取最小必要语义：

- `assistant`:
  - 文本 block -> assistant message
  - `tool_use` block -> process event
- `result`:
  - `session_id` -> session handle
  - `structured_output` -> structured result 优先来源
  - `result` -> 最终文本 / JSON fallback

不复制 Claude 全量事件语义，不向 runtime 主流程暴露 Claude 特有内部状态。

## Auth

### oauth_proxy

- 固定 callback listener:
  - `http://127.0.0.1:51123/callback`
- 默认优先 callback 模式
- 同时保留手工输入 URL / code 的 fallback
- 成功后写入：
  - `${CLAUDE_CONFIG_DIR}/.credentials.json`

### cli_delegate

- 命令：
  - `claude auth login`
  - `claude auth status`
  - `claude auth logout`
- 使用轻量会话轮询与输出锚点判定是否完成
- 不引入 Claude 专有会话状态机

## UI decoupling

管理 UI 中引擎标签、auth 入口文案、输入控件标签不再通过模板里的 engine 分支硬编码。  
改为由 `ui.py` 统一构造 `engine_ui_metadata`，模板和前端脚本只消费元数据。

这次 change 允许保留 OpenCode provider 这一层特殊性，但不再继续为新 engine 堆模板条件分支。

## Static models

Claude 模型目录使用静态 manifest / snapshot：

- `claude-sonnet-4-6`
- `claude-opus-4-6`
- `claude-haiku-4-5`

不做 runtime probe catalog。
