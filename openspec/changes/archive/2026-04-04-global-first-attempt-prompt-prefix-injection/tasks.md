# Tasks

- [x] 1.1 创建 `global-first-attempt-prompt-prefix-injection` change 工件
- [x] 1.2 补齐 proposal / design / delta spec

- [x] 2.1 在 `prompt_builder_common` 补充 engine 相对目录上下文
- [x] 2.2 在 `base_execution_adapter` 收口最终生效 prompt，并实现首 attempt 全局前缀注入
- [x] 2.3 新增静态全局前缀模板文件

- [x] 3.1 更新 prompt common 单元测试，覆盖 engine 相对目录上下文
- [x] 3.2 更新 adapter 回归测试，覆盖首 attempt 注入、非首 attempt 不注入、`__prompt_override` 与命令构建一致性
- [x] 3.3 运行目标 pytest
- [x] 3.4 运行目标 mypy
