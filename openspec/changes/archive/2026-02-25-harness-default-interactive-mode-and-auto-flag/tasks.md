## 1. CLI 参数与模式解析

- [x] 1.1 在 `agent_harness/cli.py` 为 legacy/direct 两条语法增加 `--auto`（位于 engine 之前）
- [x] 1.2 调整 CLI 默认 execution mode 为 `interactive`，并在指定 `--auto` 时切换为 `auto`
- [x] 1.3 确保 `--auto` 仅作为 harness 控制参数，不进入 passthrough

## 2. Runtime 模式贯通

- [x] 2.1 扩展 `HarnessLaunchRequest` 以携带 execution mode
- [x] 2.2 在 `agent_harness/runtime.py` 中将 execution mode 贯通到配置注入与技能补丁注入调用
- [x] 2.3 扩展 handle metadata：start 写入 execution mode，resume 读取并继承
- [x] 2.4 兼容旧 handle：缺失 execution mode 时回退为 `interactive`

## 3. Skill 注入与审计

- [x] 3.1 扩展 `agent_harness/skill_injection.py` 注入接口，支持按 execution mode 注入 patch
- [x] 3.2 在 `.audit/meta.N.json` 的 launch payload 中记录 execution mode
- [x] 3.3 校验 translate 与 execution mode 控制参数语义隔离不回退

## 4. 测试与文档回归

- [x] 4.1 更新 `tests/unit/test_agent_harness_cli.py`：覆盖默认 interactive 与 `--auto` 两条路径
- [x] 4.2 更新 `tests/unit/test_agent_harness_runtime.py`：覆盖 mode 贯通、resume 继承与旧 handle 回退
- [x] 4.3 运行 Harness 相关单测并修复回归
- [x] 4.4 更新 harness 使用文档/示例命令，标注默认模式变更与 `--auto` 迁移方式
