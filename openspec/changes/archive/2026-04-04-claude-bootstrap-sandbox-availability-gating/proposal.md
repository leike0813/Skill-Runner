# claude-bootstrap-sandbox-availability-gating Proposal

## Summary

在服务启动 bootstrap 阶段为 Claude 增加真实的 sandbox 可用性探测。只有 probe 成功时，常规 headless Claude run 才继续启用 sandbox；probe 失败时，后续 headless run 统一生成 `sandbox.enabled = false` 的 Claude settings，避免在不同宿主环境里反复命中 `RTM_NEWADDR` / namespace 级失败。

## Motivation

当前 Claude headless 运行链路只根据配置声明与依赖存在性判断 sandbox，无法识别“依赖存在但宿主不允许 bubblewrap netns/userns 初始化”的环境。结果是：

- bootstrap / UI 视图会误报 sandbox ready
- headless run 会在每次 Bash 调用时重复撞同一类 sandbox runtime failure
- 模型被迫在 run 内不断试错，而不是在服务级别一次性识别环境能力

本次 change 把判断前移到服务 bootstrap，并采用 fail-open：sandbox 不可用时继续运行 Claude，但不再为 headless run 注入无效 sandbox。

## Scope

- 在 `main.lifespan() -> AgentCliManager.ensure_layout()` 内补 Claude sandbox smoke probe
- 将 probe 结果写入 Claude bootstrap sidecar
- 用 sidecar 统一控制 Claude headless config compose 与默认 prompt 文案
- 将 Claude sandbox 状态展示从“依赖存在”升级为“真实 probe 结果”

## Non-Goals

- 不修改 Claude `ui_shell` 的独立 sandbox 策略
- 不做 per-run 重探测
- 不新增 runtime 自动 retry / restart 机制
- 不修改 FCMP / RASP / HTTP API

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
