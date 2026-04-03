# runner-common-prompt-fallback Design

## Design Overview

`entrypoint.prompts` 增加一个保留键 `common`，语义是“通用默认 prompt”。

运行时解析优先级固定为：

1. `entrypoint.prompts[engine_key]`
2. `entrypoint.prompts.common`
3. adapter 的默认模板文件
4. adapter 的 `fallback_inline`

## Runtime Resolution

实现仅修改 runtime/common prompt builder 的模板选择逻辑：

- 若 skill manifest 为当前 engine 明确声明 prompt，则继续优先使用
- 否则尝试读取 `common`
- 若 `common` 不存在，再回退到 adapter profile 提供的模板或 inline fallback

这样不会影响现有 engine-specific prompt 行为，只是给 skill 包增加一个无重复的默认入口。
