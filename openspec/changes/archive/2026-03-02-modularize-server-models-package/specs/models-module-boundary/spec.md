## MODIFIED Requirements

### Requirement: Models MUST be organized by domain modules
系统 MUST 将模型实现统一收敛在 `server/models/` 包内，并按业务领域拆分为独立模块，避免继续在 `server/` 根目录维持 `models_*.py` 平铺结构。

#### Scenario: package-based domain layout
- **WHEN** 扫描模型实现层
- **THEN** `common/run/skill/engine/interaction/management/runtime_event/error` 等领域模型 MUST 位于 `server/models/` 下
- **AND** `server/models/__init__.py` MUST 仅作为对外导出入口而非承载大段领域实现

#### Scenario: no legacy root model modules
- **WHEN** 扫描 `server/` 根目录
- **THEN** `server/models_*.py` 旧平铺模块 MUST NOT 继续存在

### Requirement: `server.models` import contract MUST remain backward compatible
系统 MUST 保持既有 `from server.models import X` 的可用性，确保本次仅改变实现位置而不改变调用方导入语义。

#### Scenario: legacy public import parity
- **WHEN** 既有代码与测试使用 `from server.models import <ModelOrEnum>`
- **THEN** 导入行为 MUST 保持可用
- **AND** 导入对象名称、字段、默认值与枚举字面量 MUST 与迁移前兼容

#### Scenario: package migration does not require API caller rewrite
- **WHEN** 仅发生 `server/models.py` 到 `server/models/` 的包化迁移
- **THEN** 对外公开导入契约 MUST 保持稳定
- **AND** 调用方 MUST NOT 因目录重构被迫修改业务语义代码

### Requirement: Model module structure MUST be guarded by tests
系统 MUST 提供结构守卫，阻止回归到 `server/` 根目录散落模型模块或在 facade 中重新堆积实现细节。

#### Scenario: structure regression blocked for root-level model files
- **WHEN** 新增 `server/models_*.py` 或将大段模型实现重新放回 facade
- **THEN** 结构守卫测试 MUST 失败并提示应迁移到 `server/models/` 包内领域模块

