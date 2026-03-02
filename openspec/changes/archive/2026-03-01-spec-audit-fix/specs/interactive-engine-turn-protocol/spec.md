# interactive-engine-turn-protocol Specification

## Purpose
定义引擎适配层的统一回合协议、ask_user 载荷校验、模式感知补丁注入和按 execution_mode 区分的完成态判定规则。

## MODIFIED Requirements

### Requirement: 引擎适配层 MUST 输出统一回合协议
The system MUST express turn results via a unified protocol, and `ask_user` MUST NOT be a hard prerequisite for entering `waiting_user` in interactive mode.

#### Scenario: ask_user 仅作为可选增强信息
- **WHEN** 引擎输出 `ask_user` 结构
- **THEN** 系统可将其解析为 pending 的增强字段（如 `ui_hints/options/context`）
- **AND** 不将其作为唯一控制流判定依据

#### Scenario: ask_user 可选增强优先使用非 JSON 结构
- **WHEN** 引擎需要输出 ask_user 风格提示
- **THEN** 应优先使用与 JSON 明显不同的结构化格式（例如 YAML block）
- **AND** 避免被最终业务 JSON 解析链误识别
