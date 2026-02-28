## Overview

本 change 采用“迁移 + 兼容”策略：

1. 先迁移文件到目标层级（runtime/engines/services 子域）。
2. 再通过 import 重定向与兼容层保障行为稳定。
3. 在 phase1 内删除确认无依赖的过时文件。

## Target Topology

### Runtime

- `server/runtime/protocol/*`
- `server/runtime/session/*`
- `server/runtime/observability/*`
- `server/runtime/execution/*`

### Engines

- `server/engines/common/openai_auth/*`（承载 OpenAI 共享协议）
- `server/engines/common/config/*`（引擎共用 JSON 分层配置生成）
- `server/engines/codex/adapter/config/*`
- `server/engines/opencode/models/*`

### Services（按域）

- `server/services/orchestration/*`
- `server/services/skill/*`
- `server/services/ui/*`
- `server/services/platform/*`

> Phase1 约束：`server/runtime/*` 是 Run Core 唯一实现层，不再保留 `services/run/*`。

## Compatibility Strategy

1. phase1 允许保留少量兼容导入层（旧路径 -> 新路径）以控制改动风险。
2. phase2 删除兼容层，切换为新路径硬依赖。
3. 对外 API 与路由不变，仅调整内部 import 与模块组织。

## Cleanup Strategy

直接删除确认过时且不应复活的文件：

- `server/services/job_orchestrator-joshua-central-safeBackup-0001.py`
- `server/services/oauth_openai_proxy_common.py`（迁移后）
- `server/services/openai_device_proxy_flow.py`（迁移后）

## Risks

1. 大量 import 路径迁移导致隐藏引用遗漏。
2. Runtime Core 迁移后，审计/协议路径回归风险。
3. auth 与 adapter 交界处的环状依赖风险。

## Mitigations

1. 先迁 runtime core，再迁 engines common，最后 services 分域。
2. 先跑 runtime SSOT 测试清单，再跑 adapter/auth/UI 回归。
3. 增加静态守卫测试，禁止关键目录回流旧依赖。
