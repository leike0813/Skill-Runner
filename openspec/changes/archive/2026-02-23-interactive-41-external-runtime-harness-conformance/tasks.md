## 1. Spec Baseline

- [x] 1.1 完成并冻结 `proposal.md`，明确“外挂实现 + 复用核心 + run 重定向”边界
- [x] 1.2 完成 `external-runtime-harness-cli` 规范
- [x] 1.3 完成 `external-runtime-harness-audit-translation` 规范
- [x] 1.4 完成 `external-runtime-harness-environment-paths` 规范

## 2. Shared Runtime Refactor

- [x] 2.1 识别并抽取可复用的运行时核心接口（环境构建、命令解析、转译入口）
- [x] 2.2 以最小改动方式让主服务链路与 harness 共用核心接口
- [x] 2.3 增加 capability-gated 引擎能力检查（含 opencode 预留）

## 3. Harness CLI Implementation

- [x] 3.1 新增外挂 harness 目录与 CLI 入口（独立于 `server/`）
- [x] 3.2 实现 `start` 命令：passthrough 参数透传、run selector 支持
- [x] 3.3 实现 `resume` 命令：handle 解析、会话恢复、消息续写
- [x] 3.4 实现 `--translate 0|1|2|3` 输出分级，且不透传给引擎

## 4. Environment and Path Wiring

- [x] 4.1 对齐 `scripts/deploy_local.sh` 的默认环境语义读取
- [x] 4.2 实现默认 run root `data/harness_runs/`
- [x] 4.3 实现 harness run root 的环境变量覆盖
- [x] 4.4 增加启动前环境与可执行文件自检（结构化错误输出）

## 5. Audit and Conformance Report

- [x] 5.1 复用项目核心 RASP/FCMP 转译链路生成事件视图
- [x] 5.2 产出按 attempt 组织的审计工件（不落盘 fd-trace）
- [x] 5.3 生成一致性报告（parser/FCMP/diagnostics/completion 摘要）

## 6. Tests and Verification

- [x] 6.1 新增 harness CLI 单元测试（translate、passthrough、resume、run selector）
- [x] 6.2 新增环境路径测试（默认继承、run root 隔离、覆盖变量）
- [x] 6.3 新增审计与转译一致性测试（与核心协议字段对齐）
- [x] 6.4 执行全量单元测试并修复回归
- [x] 6.5 执行 OpenSpec 校验并推进至 apply-ready

## 7. Integration Test Adoption

- [x] 7.1 将引擎执行链路集成测试统一迁移为 harness fixture 驱动
- [x] 7.2 将 API/UI 契约集成测试从引擎集成测试目录中拆分到独立目录
- [x] 7.3 同步更新引擎集成与 API 集成的脚本入口与文档指引，避免混淆

## 8. Post-Implementation Drift Alignment

- [x] 8.1 补充 CLI 直连语法（`agent_harness <engine> ...`）与兼容 `start/resume` 的规范说明
- [x] 8.2 补充 `translate=0 + TTY` 实时透传行为说明
- [x] 8.3 补充 util-linux `script` 参数兼容约束（`--log-out` 下不追加 typescript 位置参数）
- [x] 8.4 补充运行输出边界分隔符与精简尾部摘要输出规范（对齐 `agent-test-env`）
- [x] 8.5 对齐 `translate=3` 终端输出为 Simulated Frontend View (Markdown)，并明确一致性报告继续落盘
- [x] 8.6 对齐 `translate=3` 待输入渲染：抑制默认英文 prompt 行，仅保留本地化占位提示
- [x] 8.7 对齐主服务 trust 生命周期：Codex/Gemini 运行前注入 trust、运行后清理 trust
- [x] 8.8 对齐分隔符行为：runtime begin/end 单次出现且包裹 translate 输出，移除 CLI 二次 translated 分隔符
- [x] 8.9 补充 harness skill 注入：运行前同时注入项目 `skills/` 与 `tests/fixtures/skills/`，并将注入摘要落盘到审计 meta
- [x] 8.10 对齐 `agent-test-env` 运行前审计输出：在 runtime begin 前打印 run_id/run_dir/executable/passthrough/translate_mode/injected_skills/config_roots
- [x] 8.11 补充 harness 执行前配置注入：复用 API 同类注入能力（enforced-only），并为 Codex 使用独立 profile `skill-runner-harness`
- [x] 8.12 修复 Gemini 解析：支持多行 JSON 文档解析，采用 split 流优先且 PTY 仅兜底，避免重复消费导致 raw 事件膨胀
