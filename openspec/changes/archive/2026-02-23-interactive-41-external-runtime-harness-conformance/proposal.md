## Why

当前项目缺少一套“外挂式”的本地一致性验证框架，无法在不影响主服务链路的前提下，持续验证本项目运行时解析/转译行为与已验证参考实现（`references/agent-test-env`）的一致性。  
随着交互执行、审计与前端消息协议复杂度上升，需要一个可独立运行、可回归、可审计的 harness 来降低回归风险。

## What Changes

- 新增外挂式 runtime harness（独立目录与独立 CLI），默认不影响主服务运行路径与现有 API。
- harness 运行时 MUST 复用本项目核心运行时能力（环境构建、引擎执行、审计、RASP/FCMP 转译），禁止再实现一套平行核心逻辑。
- 新增与 `agent-test-env` 对齐的 CLI 体验：
  - 兼容 `start` / `resume`；
  - 直接引擎语法（`agent_harness <engine> ...`）；
  - 参数透传；
  - `--translate 0|1|2|3` 多级输出；
  - `translate=0 + TTY` 实时透传；
  - handle 级 resume。
- 新增默认环境与路径策略：
  - 默认继承 `scripts/deploy_local.sh` 的 managed prefix 相关环境；
  - run root 默认重定向到 `data/harness_runs/`，并支持环境变量覆盖。
- 新增 harness skill 注入：
  - 运行前将项目根目录 `skills/` 与 `tests/fixtures/skills/` 下的 skill 包注入到引擎工作目录（按引擎映射到 `.codex/.gemini/.iflow/.opencode` 技能目录）；
  - 注入后的 `SKILL.md` 追加运行完成约束（completion contract），保持与主项目运行时约束一致。
- 新增一致性审计报告输出（面向解析/转译对齐验证）。
- 明确 PTY 录制参数兼容策略：使用 `script --log-out` 时不追加额外 typescript 位置参数，避免 util-linux 参数冲突。
- 将“引擎执行链路集成测试”统一改为通过 harness 夹具执行，并与 API/UI 契约测试物理分层，避免测试语义混淆。
- 预留 `opencode` 引擎位：在后端具备对应能力时可直接纳入，不具备时给出明确能力不足错误。

## Capabilities

### New Capabilities
- `external-runtime-harness-cli`: 定义外挂 harness 的 CLI 入口、参数透传、translate 分级与 resume 行为。
- `external-runtime-harness-audit-translation`: 定义 harness 的审计工件、RASP/FCMP 转译复用与一致性报告输出。
- `external-runtime-harness-environment-paths`: 定义 harness 默认环境继承、managed prefix 复用与 run root 重定向规则。
- `external-runtime-harness-test-adoption`: 定义引擎集成测试接入夹具与测试分层规则。

### Modified Capabilities
- 无。

## Impact

- Affected code (expected):
  - 新增外挂目录（建议：`agent_harness/`）及其 CLI/报告模块；
  - 新增 harness skill 注入模块（汇聚项目技能与测试夹具技能）；
  - 复用并小幅重构 `server/services/` 中可抽象的核心运行时接口。
  - 调整测试目录结构：引擎执行链路测试与 API/UI 契约测试分层。
- Affected APIs:
  - 主服务对外 API 路径不变；
  - 新增 harness CLI，不新增强耦合 HTTP 接口。
- Affected systems:
  - 本地开发与回归流程新增 harness 执行入口；
  - 默认 run 数据写入 `data/harness_runs/`，与主 `data/runs/` 隔离。
