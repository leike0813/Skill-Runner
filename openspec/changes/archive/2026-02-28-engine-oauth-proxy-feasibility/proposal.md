## Why

当前引擎鉴权主要依赖内嵌 TUI 或手动复制凭据文件，操作门槛较高。团队希望评估“将引擎 OAuth 能力暴露给前端”的可行性，但各 CLI 的鉴权机制和可编排能力差异较大，贸然实现存在较高返工风险。

## What Changes

- 新增一个**纯预研** OpenSpec change，用于评估 engine 前端 OAuth 代理的技术可行性与实施边界。
- 固化四个引擎（codex/gemini/iflow/opencode）的鉴权能力证据（CLI 行为、源码/文档约束、凭据落盘路径、无头环境限制）。
- 输出统一能力矩阵与候选架构对比（CLI 委托式、原生 OAuth Broker、混合分层）。
- 输出 Go/No-Go 结论、风险分级与后续实现 change 的前置条件。
- 明确本 change **不包含运行时代码实现、不新增 API、不修改现有鉴权流程**。

## Capabilities

### New Capabilities

- `engine-oauth-proxy-feasibility`: 定义 OAuth 代理可行性评估的最小标准化产物（能力矩阵、方案对比、Go/No-Go 结论），为后续实现型 change 提供可审计输入。

### Modified Capabilities

- （无）本 change 不修改现有运行时能力 requirement，仅新增研究型 capability。

## Impact

- 影响范围仅限 `openspec/changes/engine-oauth-proxy-feasibility/` 下的预研文档。
- 不影响 `server/*`、`docs/*` 的现有实现与公开契约。
- 为后续实现型 change 提供可审计的技术决策输入，降低错误路线导致的返工成本。
