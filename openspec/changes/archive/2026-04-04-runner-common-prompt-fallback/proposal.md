# runner-common-prompt-fallback Proposal

## Summary

允许 skill 包在 `runner.json` 的 `entrypoint.prompts` 下声明一个 `common` prompt，作为所有引擎未命中 engine-specific prompt 时的默认回退。

## Motivation

当前 prompt 解析只识别精确的 engine key，导致 skill 包如果想为多个引擎复用同一份 prompt，只能重复填写多次。这个限制没有必要，也让 `runner.json` 更冗长。

## Scope

- 为 `entrypoint.prompts.common` 增加受支持的运行时语义
- 在 prompt 解析路径中增加 `common` fallback
- 补充 OpenSpec 与回归测试

## Non-Goals

- 不引入多级 prompt 继承
- 不改变 engine-specific prompt 的优先级
- 不批量改写现有 builtin skill 的 `runner.json`

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
