# claude-run-folder-trust-injection

## Why

Claude Code 的 trust folder 判定以“当前工作目录向上追溯到最近 git 仓库根”为基准，而 Skill Runner 当前的 run/session 目录通常位于仓库内层。  
如果不做额外治理，Claude 会把仓库根当成待信任目录，并在 run/auth/harness/UI shell 路径中弹出不符合预期的 trust 门禁。

另外，Claude 的 trust 持久化介质与 Codex/Gemini 不同，使用 `~/.claude.json.projects` 记录项目状态。现有 run-folder trust lifecycle 尚未覆盖该介质。

## What Changes

- 为所有 engine 的 run/session 目录增加统一的最小 git repo bootstrap，确保 `run_dir/.git` 存在
- 为 Claude 新增 adapter-local trust folder strategy，持久化到 `agent_home/.claude.json`
- 将 Claude 纳入 API run、auth session、agent harness、UI shell 的 run-scope trust 生命周期
- 保持 cleanup 为 best-effort，不影响 terminal status
- 保持 Claude parent trust bootstrap 为 no-op，不将 runs root 长期注入 `.claude.json`

## Impact

- Claude 在 run/auth/harness/UI shell 路径中将以 run/session 目录为 trust 根，而不是仓库根
- 所有 engine 的 run/session 目录都会多一个最小 `.git/`
- `.git/` 将从 filesystem snapshot / diff 中忽略，避免污染审计输出
