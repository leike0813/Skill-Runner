## Why

当前配置与契约存在分散读取与目录职责混杂：

- 并发策略通过独立 JSON 文件加载，未纳入 YACS 主配置。
- 引擎能力配置（命令 profile、鉴权策略）集中在全局 `assets/configs`，与 engine 代码分离。
- 机器执行 schema 与行为合同分散在 `server/assets/schemas` 与 `docs/contracts`。

这导致路径硬编码、治理成本高、后续扩展时容易行为漂移。

## What Changes

- 保留 YACS，新增 `SYSTEM.CONCURRENCY.*`，并将并发策略切换为 YACS 唯一真源。
- 新增统一配置读取层（registry/loaders），收口策略与契约文件读取入口。
- 引擎能力配置迁移到 `server/engines/<engine>/config/`：
  - `command_profile.json`
  - `auth_strategy.yaml`
- 新增 `server/contracts/{schemas,invariants}` 作为契约 canonical 路径；读取改为新路径优先、旧路径回退（phase-1）。
- 更新关键文档中的契约路径引用。

## Capabilities

### New

- `config-and-contract-governance`: 统一配置分层职责与契约读取入口。

### Modified

- `job-orchestrator-modularization`: 并发策略读取与运行时契约读取来源治理化。
- `engine-auth-observability`: 鉴权策略来源从单一全局文件转为引擎配置聚合。

## Impact

- 外部 API 无变更。
- 内部配置加载与路径管理发生结构化重构。
