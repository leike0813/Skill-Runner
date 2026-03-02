## ADDED Requirements

### Requirement: Models MUST be organized by domain modules
系统 MUST 将当前集中于 `server/models.py` 的模型定义按业务领域拆分为多个模块，并避免继续在单文件内扩张。

#### Scenario: domain split structure
- **WHEN** 扫描模型实现层
- **THEN** run/skill/engine/interaction/management/runtime-event/common 等领域模型 MUST 位于独立模块
- **AND** `server/models.py` MUST 不再承载大段领域实现

### Requirement: `server.models` import contract MUST remain backward compatible
系统 MUST 保持既有 `from server.models import X` 的可用性，避免大范围调用方破坏。

#### Scenario: legacy imports continue to work
- **WHEN** 既有代码与测试使用 `from server.models import <ModelOrEnum>`
- **THEN** 导入行为 MUST 保持可用
- **AND** 导入对象的名称、字段、默认值与枚举字面量 MUST 与重构前兼容

### Requirement: Runtime and API schema semantics MUST remain unchanged
模型拆分 MUST 仅改变实现位置，不改变协议与接口语义。

#### Scenario: runtime event schema parity
- **WHEN** runtime 协议相关代码序列化/反序列化事件模型
- **THEN** 事件 envelope、category/type、raw_ref 等字段语义 MUST 保持不变

#### Scenario: management and interactive payload parity
- **WHEN** management 与 interactive API 返回/接收对应模型
- **THEN** 字段名、可选性、默认值与校验行为 MUST 保持兼容

### Requirement: Model module structure MUST be guarded by tests
系统 MUST 提供结构守卫，防止 `server/models.py` 再次演化为 god-file。

#### Scenario: structure regression blocked
- **WHEN** 新增模型定义直接堆叠到 `server/models.py`
- **THEN** 结构守卫测试 MUST 失败并提示应迁移至领域模块
