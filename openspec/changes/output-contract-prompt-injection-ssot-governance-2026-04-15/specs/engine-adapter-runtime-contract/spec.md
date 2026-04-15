## ADDED Requirements

### Requirement: Structured output pipeline MUST align machine schema transport and prompt contract rendering
系统 MUST 通过统一 structured-output pipeline 决定引擎实际使用的 machine schema 与对应 prompt contract 文本，禁止两者分别由不同调用点独立选择。

#### Scenario: canonical passthrough engine
- **WHEN** 某引擎使用 canonical passthrough 策略
- **THEN** CLI schema 注入 MUST 使用 canonical machine schema
- **AND** prompt contract rendering MUST 使用 canonical schema 派生文本

#### Scenario: compat-translated engine
- **WHEN** 某引擎使用 compat translate 策略
- **THEN** CLI schema 注入 MUST 使用 engine-effective compat schema
- **AND** prompt contract rendering MUST 使用与该 compat schema 一致的派生文本

### Requirement: Engine adapters MUST consume prompt contract text as in-memory runtime data
系统 MUST 将 prompt contract 文本视为 structured-output pipeline 的内存结果，而不是 run-scoped Markdown artifact 路径。

#### Scenario: adapter or patch consumer requests prompt contract
- **WHEN** adapter bootstrap、skill patcher 或 repair builder 请求 prompt contract
- **THEN** 返回值 MUST 为内存中的 rendered contract text
- **AND** 系统 MUST NOT 依赖 `.audit/contracts/*.md` prompt artifact path
