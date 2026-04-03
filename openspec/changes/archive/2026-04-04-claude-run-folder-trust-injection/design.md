# Design

## Decisions

### 1. Trust 生命周期保持 run-scope

Claude 采用与 Codex/Gemini 相同的 run/session 生命周期：

- CLI 调用前注册 trust
- run/session 结束后删除 trust
- cleanup 失败只记 warning，不改变终态

这保证 trust 不会在 managed agent home 中无限累积。

### 2. 先 bootstrap git，再做 trust 注册

Claude 的 project path 解析优先使用最近 git root。  
因此如果直接在仓库内层 run 目录执行 Claude，它会追溯到仓库根并要求信任错误的目录。

解决方式不是修改 Claude 行为，而是在所有 engine 的 run/session 目录统一执行最小 git bootstrap：

- 若 `run_dir/.git` 已存在，保持幂等
- 若不存在，执行最小 `git init -q <run_dir>`

这样 Claude 会把 `run_dir` 识别为最近 git root。

### 3. Claude trust 介质采用 `.claude.json.projects`

Claude strategy 使用 `agent_home/.claude.json` 作为持久化文件：

- 缺失或非法时修复为 object
- `projects` 缺失或非法时修复为 object
- run trust 键为绝对路径字符串

为了真正跳过 trust dialog，本轮最小可行 payload 采用：

```json
{
  "projects": {
    "<abs_run_dir>": {
      "hasTrustDialogAccepted": true
    }
  }
}
```

本轮不补写 `allowedTools`、usage metrics 或 onboarding 字段。

### 4. Claude parent trust bootstrap 为 no-op

Codex/Gemini 允许对 runs parent 做长期 trust bootstrap；Claude 不这么做。  
因为 Claude 的 trust 以 project root 组织，而本轮目标是 run/session 级动态注入，不把 `${RUNS_DIR}` 作为长期信任根。

### 5. 不在 manager 主干写 engine-specific 分支

Claude 的 trust 逻辑放在：

- `server/engines/claude/adapter/trust_folder_strategy.py`

集中接入点只扩展 registry：

- `server/engines/common/trust_registry.py`

`RunFolderTrustManager` 继续只做 dispatch，不引入 `if engine == "claude"`。

## Affected Paths

- API run lifecycle
- auth session lifecycle
- agent harness
- UI shell session
- filesystem snapshot ignore rules
