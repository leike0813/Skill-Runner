## MODIFIED Requirements

### Requirement: Temporary skill execution MUST bind to shared execution core via temp source adapter
临时 skill 链路（`/v1/temp-skill-runs*`）MUST 通过 `temp` source adapter 接入统一执行核心，同时保留临时 skill 专属生命周期职责。

#### Scenario: Temporary upload/start reuses shared core while preserving temp lifecycle
- **WHEN** 客户端调用临时链路 create 与 upload
- **THEN** 通用校验、缓存策略、调度与状态回写逻辑由统一核心执行
- **AND** skill 包 staging/清理、临时目录生命周期由 temp source adapter 独立处理

#### Scenario: Temporary source MUST expose parity interaction/history/range capabilities
- **WHEN** 客户端调用临时链路 pending/reply/history/range 能力
- **THEN** 这些能力必须可用
- **AND** 参数校验、状态约束与错误语义与常规链路保持一致
