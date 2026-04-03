## 1. OpenSpec

- [x] 1.1 创建 `claude-runtime-parser-semantics-and-resume` change 工件
- [x] 1.2 补齐 proposal / design / delta specs

## 2. Claude parser

- [x] 2.1 让 Claude parser 从 `system/init` 稳定提取 `run_handle`
- [x] 2.2 将 Claude `tool_use` / `tool_result` 分类收口到 `tool_call` / `command_execution`
- [x] 2.3 补齐 `assistant_messages` 与 `turn_markers` 回归
- [x] 2.4 将 `assistant.message.content[type=thinking]` 归类为 `reasoning`

## 3. Resume contract

- [x] 3.1 对齐 Claude resume 的 harness / regression 命令口径为 `--resume <session-id>`

## 4. Validation

- [x] 4.1 更新/新增 Claude parser 与 harness 测试
- [x] 4.2 运行目标 pytest
- [x] 4.3 运行目标 mypy
