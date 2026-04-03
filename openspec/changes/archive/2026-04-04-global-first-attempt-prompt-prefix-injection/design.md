# Design: global-first-attempt-prompt-prefix-injection

## Summary
实现拆成两层：

1. `prompt_builder_common` 负责为模板上下文补充 engine 维度变量：
   - `engine_id`
   - `engine_workspace_dir`
   - `engine_skills_dir`
2. `base_execution_adapter` 负责统一解析最终生效 prompt：
   - 先渲染原始 prompt
   - 再应用 `__prompt_override`
   - 仅当 `__attempt_number == 1` 时 prepend 全局前缀模板

## Decisions
- 全局前缀来源固定为仓库静态模板文件，不接 management settings
- 前缀注入点放在最终 prompt 层，而不是只改默认模板
- engine 目录提示采用固定相对路径形式，如 `./.codex/skills`
- 前缀与原 prompt 之间固定插入一个空行

## Non-Goals
- 不新增系统设置或 UI 配置入口
- 不修改 adapter profile schema
- 不改 runtime 协议与 HTTP API
