## Context

本变更是对 `opencode` 后端接入的收敛性补档：代码与测试已落地，OpenSpec 需补齐“从占位到正式”的行为定义，避免实现与规范脱节。

## Decisions

1. 命令基线与 `agent-test-env` 保持一致：
   - 首次执行：`opencode run --format json --model <provider/model> '<prompt>'`
   - 续跑执行：`opencode run --session=<session_id> --format json --model <provider/model> '<message>'`
2. interactive 首版仅支持 `session` 续跑，不引入额外恢复模式。
3. `opencode` 模型字符串强制 `<provider>/<model>`，不支持 `@effort`。
4. 模型来源以 `opencode models` 为 SSOT，服务端维护本地缓存并在后台异步刷新。
5. `/ui/engines` 与内联终端作为同级引擎入口纳入 `opencode`。
6. 保持 FCMP 事件类型不扩展：`opencode_ndjson` 仅映射到既有语义。
7. 技能目录统一使用 `.opencode/skills/`，并在 FS diff 中加入 `.opencode/` 忽略。
8. 运行环境注入 XDG 目录映射：
   - `XDG_CONFIG_HOME=<agent_home>/.config`
   - `XDG_DATA_HOME=<agent_home>/.local/share`
   - `XDG_STATE_HOME=<agent_home>/.local/state`
   - `XDG_CACHE_HOME=<agent_home>/.cache`
9. opencode 配置/鉴权文件映射固定为：
   - `auth.json` -> `<agent_home>/.local/share/opencode/auth.json`
   - `opencode.json` -> `<agent_home>/.config/opencode/opencode.json`
   - `antigravity-accounts.json` -> `<agent_home>/.config/opencode/antigravity-accounts.json`
10. `auth_ready` 规则锁定：
    - `opencode auth_ready = (CLI可用) AND (auth.json存在)`
    - `antigravity-accounts.json` 仅作附加诊断，不是 ready 必要条件。
11. 默认插件配置写入全局基线：
    - `plugin: ["opencode-antigravity-auth"]`

## Rationale

- 与 `agent-test-env` 命令约定对齐可降低环境差异导致的执行偏差。
- 先以 `session` 续跑打通 interactive 主路径，再迭代更复杂恢复策略，可控制风险。
- 明确模型格式可避免 `provider` 语义丢失，也避免误用 codex 的 `@effort` 语法。
- `opencode models` 可反映“已登录 provider 集合”，更适合作为动态模型来源。
- XDG 映射 + 导入规则固定后，可保留“手工复制鉴权文件即可生效”的运维路径。
- 不新增 FCMP 事件类型可减少协议面变更成本，维持现有消费端稳定性。

## Non-Goals

1. 本次不引入 `@effort`、provider alias 或项目内 auth 自动同步。
2. 本次不扩展新的 FCMP 事件类型。
3. 本次不新增第二套 opencode 专属交互状态机。
