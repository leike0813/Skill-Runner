## Why

当前 runtime 有两个可观测性/执行语义缺口：

1. terminal 失败时，FCMP 与 orchestrator 审计里经常只有 `failed`，缺少稳定错误摘要，排障成本高。  
2. `skill.runtime.dependencies` 已在 manifest 模型中存在，但执行链路未在 agent 启动前统一尝试依赖注入，和既有设计语义不一致。

## What Changes

- terminal 失败收敛时，统一产出 `code + message(summary)` 并写入 `lifecycle.run.terminal`。  
- FCMP terminal 映射优先使用 terminal orchestrator payload 的错误摘要。  
- adapter 在执行命令前尝试基于 `runtime.dependencies` 的 `uv` 注入探测：
  - 探测成功：使用 `uv run --with ... -- <agent command>`。
  - 探测失败：记录结构化 warning 并回退到原始命令（best-effort fallback）。
- 同步更新 runtime schema / OpenSpec / 文档，使语义与实现一致。

## Impact

- 对外 HTTP API 不变。  
- 事件结构为向后兼容扩展（terminal orchestrator data 可选 `code/message`）。  
- run 状态机语义不变，仅增强 terminal 可观测性与依赖注入执行前置行为。
