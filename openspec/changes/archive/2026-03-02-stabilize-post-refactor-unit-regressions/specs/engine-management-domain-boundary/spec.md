## MODIFIED Requirements

### Requirement: Runtime/service/router imports MUST switch to the new package
系统 MUST 一次性完成对迁移模块的全仓依赖切换，并维持清晰的域边界。

#### Scenario: Runtime observability respects orchestration boundary
- **WHEN** runtime observability needs a job-control protocol
- **THEN** it MUST depend on a runtime-neutral/shared port definition
- **AND** `server/runtime/*` MUST NOT import `server.services.orchestration.*`
