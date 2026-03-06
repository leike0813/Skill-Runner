# Proposal: harden-agent-cli-process-lifecycle-governance

## Why
Run attempt、会话鉴权、UI TUI 各自维护子进程生命周期，终止策略和清理时机分散，服务重启后缺少统一 orphan 清理与对账入口，存在进程泄露风险。

## What Changes
- 新增统一进程治理组件：lease store + supervisor + termination。
- run/auth/ui 三条链路全部接入 lease register/release。
- 启动期执行已登记 lease 的 orphan 进程清理，再执行 run 恢复。
- 引入周期 sweep，自动回收已退出进程对应 lease。

## Scope
- 不改外部 API。
- 不改 FCMP/RASP 协议语义。
- 仅增强进程生命周期治理与可观测性。
