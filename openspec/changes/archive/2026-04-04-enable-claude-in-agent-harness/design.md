## Context

Claude engine 已经接入主系统的统一 adapter registry，但 `agent_harness` 仍有本地 `SUPPORTED_ENGINES` 白名单，因此在进入共享 adapter 路径之前就被提前拒绝。问题不在 Claude adapter 本身，而在 harness 与主系统的 engine 集合同步不完整。

## Goals / Non-Goals

**Goals:**
- 让 harness 接受 `claude` 并走现有共享 adapter 路径
- 保持 harness 的 `use_profile_defaults=False` 与 passthrough 语义不变
- 增加最小回归测试覆盖 start / resume / CLI 入口

**Non-Goals:**
- 不重做 Claude engine 本身
- 不新增 Claude 专属 harness config 注入
- 不在本轮对 trust 相关能力作新承诺

## Decisions

### 决策 1：最小修复 harness 白名单
- 方案：仅把 `claude` 加入 harness 本地支持集合，保持 `_resolve_adapter()` 继续走 registry
- 原因：根因是白名单过期，不需要再引入新的抽象

### 决策 2：继续复用共享 adapter 路径
- 方案：`start()` / `resume()` 对 `claude` 继续走 `engine_adapter_registry` 与 `build_start_command` / `build_resume_command`
- 原因：这样能保证 harness 与主系统对同一 engine 的命令构建逻辑一致

### 决策 3：不新增 Claude 专属 harness 注入
- 方案：保留现有 codex-only 注入逻辑，Claude 走非 codex 的通用路径
- 原因：本次目标是消除 unsupported，不把额外策略混进来

## Risks / Trade-offs

- [Risk] harness 只修了白名单，未来仍可能再次与主系统 engine 集合漂移 -> Mitigation：补回归测试，固定 Claude 为合法 engine
- [Risk] resume 路径缺少 Claude 回归可能导致白名单只修 start 不修 resume -> Mitigation：增加 Claude resume 测试
