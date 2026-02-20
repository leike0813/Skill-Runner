## ADDED Requirements

### Requirement: Skill 管理接口 MUST 返回可枚举的有效引擎集合
系统 MUST 在 Skill 管理相关接口中返回可供前端直接枚举的 `effective_engines`，并保留声明字段用于解释来源。

#### Scenario: 显式 allow-list 与 deny-list
- **WHEN** Skill 同时声明 `engines` 与 `unsupport_engine`
- **THEN** 管理接口返回计算后的 `effective_engines`
- **AND** 返回原始声明字段（`engines`、`unsupport_engine`）供前端展示

#### Scenario: 缺失 engines 的默认枚举
- **WHEN** Skill 未声明 `engines`
- **THEN** 管理接口将系统支持引擎减去 `unsupport_engine` 后作为 `effective_engines` 返回
- **AND** 前端无需自行推断默认引擎集合
