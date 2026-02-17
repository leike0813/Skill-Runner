## 1. 协议与模型

- [x] 1.0 前置检查：`interactive-05-engine-session-resume-compatibility` 已提供 `interactive_profile` 分层与句柄协议
- [x] 1.1 新增 `AdapterTurnResult` 与 `interaction` 子模型
- [x] 1.2 在 `EngineAdapter` 中引入回合级返回契约
- [x] 1.3 保持现有 auto 路径兼容（无 ask_user 时不变）

## 2. 三引擎适配

- [x] 2.1 Codex：补充 ask_user envelope 解析
- [x] 2.2 Gemini：补充 ask_user envelope 解析
- [x] 2.3 iFlow：补充 ask_user envelope 解析
- [x] 2.4 三引擎命令构造增加 `execution_mode` 入参
- [x] 2.5 auto 模式保留自动执行参数（Gemini/iFlow=`--yolo`; Codex=`--full-auto|--yolo`）
- [x] 2.6 interactive 模式移除自动执行参数（Gemini/iFlow 不带 `--yolo`; Codex 不带 `--full-auto/--yolo`）
- [x] 2.7 resume 回合沿用 interactive 规则，不注入自动执行参数

## 3. Patcher 策略

- [x] 3.1 `skill_patcher` 增加 execution_mode 入参
- [x] 3.2 将 patch 流程拆分为 `artifact_patch` 与 `mode_patch`
- [x] 3.3 固定执行顺序：`artifact_patch -> mode_patch`
- [x] 3.4 `artifact_patch` 在 auto/interactive 两种模式均执行
- [x] 3.5 `mode_patch` 按模式分支：auto 禁止提问；interactive 允许 ask_user 且要求结构化 interaction

## 4. 测试

- [x] 4.1 单测：ask_user 有效载荷可被解析
- [x] 4.2 单测：ask_user 非法载荷按 error 处理
- [x] 4.3 回归：auto 模式下 patcher 仍禁止交互提问
- [x] 4.4 单测：Gemini/iFlow interactive 命令不包含 `--yolo`
- [x] 4.5 单测：Codex interactive 命令不包含 `--full-auto/--yolo`
- [x] 4.6 单测：auto 命令仍包含既有自动执行参数
- [x] 4.7 单测：interactive patch 文案不包含“禁止提问”指令
- [x] 4.8 单测：两种模式均包含 artifact 重定向段
