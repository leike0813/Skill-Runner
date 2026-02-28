## Why

`server/services` 目录长期扁平堆叠，已承载运行时协议、鉴权、执行编排、技能管理、UI 管理等异构职责。随着 `server/runtime/*` 与 `server/engines/*` 架构成型，现有扁平 services 成为主要耦合与维护负担来源。

此外，仍存在明确过时实现与桥接残留（如 `job_orchestrator-*-safeBackup-*`、OpenAI 协议在 services 的旧位置），与当前分层目标不一致。

## What Changes

1. 将 services 按域分包（orchestration/skill/ui/platform），并取消 `services/run` 目录。
2. 将 Runtime Core 模块迁移至 `server/runtime/*`，作为 Run Core 唯一实现层：
   - protocol
   - session
   - observability
   - execution
3. 将 OpenAI 共用协议实现从 services 迁移到 `server/engines/common/openai_auth/*`，停止转发包装。
4. 删除确认过时文件（backup 与废弃桥接）。
5. 将引擎相关配置与模型目录能力下沉至 `server/engines/*`（codex config / common JSON config / opencode model catalog）。
5. 对外 `/v1` 与 `/ui` 接口语义保持兼容。

## Scope

### In Scope

- 目录重组与 import 迁移。
- Runtime Core 下沉与 Engines/common 协议归位。
- services 扁平化治理与过时代码清理。
- 相关测试与开发文档同步。

### Out of Scope

- 不新增对外 API。
- 不变更鉴权协议业务语义。
- 不新增 engine/provider 能力。

## Success Criteria

1. `server/services` 不再扁平承载核心运行时协议实现。
2. Runtime Core 主要模块位于 `server/runtime/*` 并稳定被调用。
3. OpenAI 协议 SSOT 位于 `server/engines/common/openai_auth/*`。
4. 过时文件被删除且无运行依赖残留。
5. 主规格与实现保持一致，关键回归测试通过。
