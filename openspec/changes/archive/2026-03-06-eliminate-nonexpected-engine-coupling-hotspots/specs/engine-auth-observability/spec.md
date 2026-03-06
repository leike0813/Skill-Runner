## ADDED Requirements

### Requirement: Auth detection service SHALL resolve detectors through registry injection
Auth detection service MUST resolve engine detectors through detector registry injection and MUST NOT directly import per-engine detector implementations.

#### Scenario: 运行 auth detection
- **WHEN** 传入 engine 进行鉴权检测
- **THEN** 服务从 detector registry 解析 detector
- **AND** 对未知 engine 返回降级结果而非直接依赖静态 import 分支
