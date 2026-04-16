## Summary

这轮采用“原位封存 + 真源断线”的做法：

- `server/engines/iflow/` 保留原位，视为封存实现。
- 所有当前支持引擎真源统一摘掉 `iflow`。
- 旧 run 的 `.iflow` 可见性改由只读兼容常量维持，不能再依赖 `ENGINE_KEYS`。

## Decisions

### 1. 活跃支持真源

以下位置视为活跃支持真源，必须同步移除 `iflow`：

- `server/config_registry/keys.py`
- engine catalog / model registry / engine policy
- engine adapter registry
- engine auth bootstrap
- auth detector registry
- UI / e2e engine 列表与 provider 映射
- engine upgrade 支持列表
- active schema/contract 的 engine 枚举

### 2. 只读兼容边界

历史 run 兼容只覆盖：

- `.iflow` 工作区目录的文件浏览与快照忽略
- 旧 run 聊天/审计详情读取

历史兼容不覆盖：

- 新建 run
- resume/restart
- engine auth
- engine upgrade
- 模型选择

### 3. 测试策略

- 通用测试改成不再把 `iflow` 视为受支持引擎。
- iflow 专属测试统一标记为 skipped，理由是 engine 已 deprecated 且实现封存，不再属于默认活跃回归。

## Risks

- 如果只从 `ENGINE_KEYS` 删除 `iflow`，而不补只读兼容名单，历史 `.iflow` 目录会丢失快照忽略和旧 run 浏览一致性。
- 如果只改 UI 而不改 schema/engine policy，`runner.json` 与 skill manifest 仍可能继续接受 `iflow`。
