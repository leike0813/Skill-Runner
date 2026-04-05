## Why

这轮实现已经把原先仅服务 `opencode` 的多 provider 鉴权、模型元数据和 UI 选择逻辑提升为通用的 provider-aware engine 模式，并让 `qwen` 复用了这条共享路径。  
但现有 OpenSpec 仍主要把这些变化写在 `2026-04-04-add-qwen-code-engine` 中，导致：

1. 共享层契约没有独立变更记录；
2. `qwen` change 混入了不属于 qwen 的公共层叙事；
3. `docs/api_reference.md` 仍把 `provider_id`、模型提交方式和鉴权导入描述成 OpenCode 特殊逻辑或旧写法优先。

## What Changes

1. 新增独立 change，记录 provider-aware 公共层契约；
2. 将共享鉴权能力矩阵、`provider_id` 主链路、provider-aware 模型与导入规则同步到相关 specs；
3. 更新 API reference：推荐 `engine + provider_id + model`，同时保留 `opencode` 旧的 `provider/model` 兼容说明；
4. 明确本 change 不引入新对外路由，只同步既有实现的公共契约与文档口径。

## Scope

### In Scope

- provider-aware engine 共享鉴权与模型契约；
- management / UI / orchestration / config-layering 相关 specs；
- `docs/api_reference.md` 中 jobs、engines、auth import/session 的对外说明；
- 与 `qwen` change 的职责边界梳理。

### Out of Scope

- 新增代码实现；
- 新增公开 HTTP 路由；
- 新增 provider 或更改既有 provider 能力矩阵。

## Impact

主要影响文档与规格归属：

- 新增 `openspec/changes/2026-04-04-generalize-provider-aware-engine-auth/**`
- 修改相关主规格的 delta specs，统一从 “OpenCode 特殊” 提升为 “provider-aware engines”
- 更新 `docs/api_reference.md`
- 为 `2026-04-04-add-qwen-code-engine` 提供公共层引用边界
