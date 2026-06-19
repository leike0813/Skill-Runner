## MODIFIED Requirements

### Requirement: Engine-specific adapter 实现 MUST 按引擎聚合

系统 MUST 将 active engine adapter 代码放置在 `server/engines/<engine>/adapter/*`，并通过 execution adapter class 装配到执行注册表。

#### Scenario: 注册活跃引擎适配器入口
- **WHEN** 系统初始化 `EngineAdapterRegistry`
- **THEN** 适配器实例来源为 `codex`、`opencode`、`claude`、`qwen` 的 execution adapter
- **AND** `gemini` MUST NOT be imported, validated, or registered as an active adapter
