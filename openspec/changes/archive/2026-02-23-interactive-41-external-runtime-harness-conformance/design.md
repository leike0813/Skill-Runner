## Context

项目当前已具备三类核心能力：  
1) managed prefix 与隔离环境构建；  
2) 三引擎执行与交互 resume；  
3) 运行时审计与 RASP/FCMP 转译。  

但这些能力主要内嵌于服务编排链路，缺少面向“外挂验证工具”的稳定复用入口。  
本 change 需要在不干扰主服务行为的前提下，引入独立 harness，并通过抽象复用核心模块来避免逻辑复制和长期漂移。

## Goals / Non-Goals

**Goals:**
- 提供独立的 harness 代码与 CLI，不改变主服务对外 API 行为。
- harness 执行 MUST 复用本项目核心运行时能力，不复制关键解析/转译逻辑。
- 对齐 `agent-test-env` 关键体验：passthrough、translate 分级、handle resume。
- 默认复用本地部署环境变量语义，并将 harness run root 重定向到独立目录。
- harness 运行前自动注入技能包，来源同时覆盖项目根 `skills/` 与 `tests/fixtures/skills/`。
- 将引擎执行链路集成测试统一接入 harness 夹具，并把 API/UI 契约测试与引擎集成测试做物理分层。
- 预留 opencode 引擎位，以 capability-gated 方式接入。

**Non-Goals:**
- 本 change 不把主服务改造成公开多租户平台。
- 本 change 不要求立即实现 opencode 后端执行能力本体。
- 本 change 不替换现有 e2e 客户端功能。

## Decisions

### Decision 1: 采用“外挂 CLI + 核心运行时接口”两层结构

- 新增外挂目录（建议 `agent_harness/`），仅承载：
  - CLI 参数解析；
  - 输出渲染（translate 0/1/2/3）；
  - 一致性报告聚合。
- 关键执行能力通过共享核心接口调用，避免在 harness 重写 adapter/orchestrator 核心逻辑。

**Why this over direct API-only approach**
- 仅走 HTTP API 难以覆盖“CLI 启动+透传+resume 句柄”链路细节；
- 仅走 API 也不利于与 `agent-test-env` 命令行行为逐项对照。

### Decision 2: 抽象最小可复用核心接口，保持主链路稳定

新增（或重构）共享接口时仅抽取稳定能力：
- runtime 环境构建（managed prefix/isolated env）；
- engine 命令解析与 capability 探测；
- 运行审计工件装配；
- RASP/FCMP 转译与指标汇总。

主服务和 harness 同时依赖该接口，实现 DRY 并降低漂移风险。

### Decision 3: 环境继承采用 deploy_local 同源语义

harness 默认读取并继承以下语义等价环境：
- `SKILL_RUNNER_DATA_DIR`
- `SKILL_RUNNER_AGENT_CACHE_DIR`
- `SKILL_RUNNER_AGENT_HOME`
- `SKILL_RUNNER_NPM_PREFIX`
- `NPM_CONFIG_PREFIX`
- `UV_CACHE_DIR`
- `UV_PROJECT_ENVIRONMENT`

同时引入 harness 专属 run root 配置（默认 `data/harness_runs/`，可覆盖），确保与主 `data/runs/` 隔离。

### Decision 4: translate 分级与 resume 行为与参考实现对齐

- `--translate` 支持 `0|1|2|3`，且该参数只用于 harness 视图控制，不得透传给引擎。
- `resume <handle> <message>` 继承 handle 对应的 translate 模式（可显式覆盖时按 CLI 规则处理）。
- run selector / handle8 查找规则在 harness 内稳定定义并审计落盘。

### Decision 5: CLI 语法对齐原生引擎命令体验

- harness 同时支持两类入口：
  - 兼容入口：`start <engine> ...` / `resume <handle> ...`
  - 直连入口：`<engine> [passthrough-args...]`
- 直连入口在参数语义上对齐“直接执行引擎命令”，但运行环境固定为 managed prefix，且仍保留 harness 审计与转译能力。

### Decision 6: translate=0 在真实终端下采用实时透传

- 当 `translate=0` 且 stdin/stdout/stderr 全部为 TTY 时，harness 采用实时透传运行，保证交互体验与原生 CLI 一致。
- 当不满足 TTY 条件或 translate>0 时，harness 使用非实时采集并在结束后输出结构化结果。

### Decision 7: PTY 录制参数遵循 util-linux script 兼容约束

- 在使用 `script --log-out` 记录 PTY 输出时，不追加额外 typescript 位置参数，避免 util-linux 参数冲突。
- 该约束作为运行时命令构建的稳定行为，避免不同 Linux 发行版之间出现启动漂移。

### Decision 8: opencode 采用 capability-gated 预留

- harness CLI 接受 `opencode` 作为合法引擎标识；
- 若共享核心尚未提供 opencode 执行能力，返回结构化 `ENGINE_CAPABILITY_UNAVAILABLE`；
- 一旦后端补齐 opencode 能力，无需重设计 harness 协议。

### Decision 9: 测试体系按“执行链路 vs 契约链路”分层

- 引擎执行链路集成测试（skills + adapters + orchestrator）统一通过 harness fixture 驱动。
- API/UI 契约集成测试保持 TestClient/monkeypatch 模式，独立目录维护。
- 两者在目录、脚本入口、文档中明确分离，避免将“引擎执行问题”与“接口契约问题”混为同一类失败。

**Why this over full unification**
- API 契约测试不需要真实引擎执行，强行并入 harness 会增加用例脆弱性与执行成本。
- 分层后可分别优化：执行链路看一致性与审计，契约链路看接口稳定性与错误语义。

### Decision 10: Harness 技能注入采用“双来源汇聚 + 引擎目录映射”

- harness 在每次 attempt 启动前执行技能注入，来源按顺序扫描：
  - `<project_root>/skills/`
  - `<project_root>/tests/fixtures/skills/`
- 按引擎映射注入到 run 目录私有技能根：
  - codex → `.codex/skills/`
  - gemini → `.gemini/skills/`
  - iflow → `.iflow/skills/`
  - opencode → `.opencode/skills/`
- 同名技能采用后写覆盖（fixtures 可覆盖项目同名技能），保证测试夹具技能可快速替换。
- 注入后对每个 `SKILL.md` 追加 completion contract（若未存在），确保运行完成信号约束一致。
- 注入摘要（source_roots/target_root/skill_count/skills）写入审计元数据，便于回溯。

### Decision 11: Harness 执行前配置注入采用 enforced-only，且 Codex 使用独立 profile

- harness 在每次 attempt 执行前调用引擎 adapter 的配置构建逻辑，保证与 API 链路共享同类“配置注入”能力。
- 本阶段策略为 enforced-only：不融合 skill defaults，仅注入系统 enforced 配置。
- Codex 在 harness 链路使用独立 profile 名（`skill-runner-harness`），与 API 默认 profile（`skill-runner`）隔离，避免相互覆盖。
- Gemini/iFlow 仍沿用各自运行目录内配置文件注入策略，不引入 profile 名概念。

### Decision 12: Gemini 解析采用“文档级 JSON 优先 + split 流优先，PTY 仅兜底”

- Gemini 的结构化解析优先尝试完整 JSON 文档（支持多行 pretty JSON），而非仅逐行 JSON 解析。
- 解析优先级：`stderr` 文档 → `stdout` 文档/逐行 → `pty` 文档/逐行（仅在 split 流无法得到结构化响应时启用）。
- 当 `stdout` 与 `pty` 同时包含相同结构化载荷时，优先消费 split 流，避免重复消费 PTY 导致 FCMP 原始事件膨胀。
- 保留 `GEMINI_STDOUT_NOISE`、`PTY_FALLBACK_USED`、`GEMINI_STREAM_JSON_FALLBACK_USED` 等诊断码，用于审计报告可解释性。

## Risks / Trade-offs

- [风险] 共享接口抽象过度，增加主服务理解成本  
  → Mitigation: 仅抽取已有稳定路径，禁止提前泛化。

- [风险] harness 与主服务对同一模块并发演进时出现回归  
  → Mitigation: 在 CI 增加 harness 回归任务与协议快照测试。

- [风险] 环境变量继承不完整导致本地行为偏差  
  → Mitigation: 增加环境导出快照与启动前自检。

- [风险] opencode 占位被误解为“已完整支持”  
  → Mitigation: 明确 capability-gated 错误码与文档状态。

## Migration Plan

1. 新增 change specs（CLI、审计转译、环境路径）并冻结行为边界。
2. 新建外挂目录与 CLI 骨架，接入共享核心接口。
3. 对现有 `server/services` 做最小重构，导出可复用运行时接口。
4. 实现 translate 分级与 handle resume。
5. 实现 run root 重定向与环境继承自检。
6. 输出一致性报告（解析/转译摘要 + 差异项）。
7. 迁移引擎集成测试到 harness fixture，并拆分 API/UI 契约测试目录与脚本入口。
8. 完成单元与集成回归后进入 verify/archive。

## Open Questions

- 无阻塞问题；本 change 采用当前已确认决策直接推进。
