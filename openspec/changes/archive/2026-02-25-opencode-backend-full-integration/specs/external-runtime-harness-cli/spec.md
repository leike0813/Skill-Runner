## MODIFIED Requirements

### Requirement: Harness CLI MUST 预留 opencode 引擎位并可能力降级
系统 MUST 接受 `opencode` 作为合法引擎标识，并提供与其他引擎同级的 start/resume 执行能力；当环境缺失 opencode CLI 时，MUST 返回安装或命令缺失错误而非静默降级。

#### Scenario: opencode start 走正式执行链路
- **WHEN** 用户执行 `agent_harness start opencode ...`
- **THEN** harness 通过 Adapter 生成并执行 opencode start 命令
- **AND** 不返回 `ENGINE_CAPABILITY_UNAVAILABLE`

#### Scenario: opencode resume 走正式执行链路
- **WHEN** 用户执行 `agent_harness resume <handle> <message>` 且对应 run 引擎为 opencode
- **THEN** harness 通过 Adapter resume 接口构建 `--session=<id>` 形态命令并继续执行

#### Scenario: opencode CLI 缺失时显式报错
- **WHEN** 用户执行 opencode start/resume 且运行环境缺失 opencode 可执行文件
- **THEN** harness 返回结构化缺失错误并附带可诊断信息
- **AND** MUST NOT 静默回退到其它引擎
