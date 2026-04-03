# Proposal: global-first-attempt-prompt-prefix-injection

## Summary
在所有任务提交的首个 attempt 中，对最终生效 prompt 统一做一次全局优先前置注入。

## Why
当前 prompt 生成只覆盖 skill 自带 prompt、引擎默认模板和 `__prompt_override`，缺少一个稳定的全局高优先级入口，无法为所有引擎首轮执行注入统一的执行约束。

## What Changes
- 新增一个仓库静态模板，作为首 attempt 的全局 prompt 前缀来源
- 在 adapter runtime common 中补充 engine 相对目录上下文
- 在 execution adapter 中统一收口“最终生效 prompt”，并在 attempt `1` 时 prepend 全局前缀
- 保持后续 attempt、resume reply、UI shell 不受影响

## Affected Specs
- `engine-adapter-runtime-contract`
