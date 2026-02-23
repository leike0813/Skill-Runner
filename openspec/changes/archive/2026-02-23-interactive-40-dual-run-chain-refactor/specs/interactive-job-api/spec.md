## MODIFIED Requirements

### Requirement: Regular run execution MUST bind to shared execution core via installed source adapter
常规链路（`/v1/jobs*`）MUST 通过 `installed` source adapter 接入统一执行核心，而不是维护独立重复业务实现。

#### Scenario: Regular create/upload/start reuses shared core
- **WHEN** 客户端调用常规链路 create 与 upload
- **THEN** 校验、缓存策略、调度与状态回写逻辑由统一核心执行
- **AND** router 层仅负责参数映射与 source 绑定

#### Scenario: Regular interaction/history/range semantics align with temp source
- **WHEN** 客户端调用常规链路的 pending/reply/history/range 能力
- **THEN** 行为语义以统一核心服务为准
- **AND** 与 temp 链路保持一致
