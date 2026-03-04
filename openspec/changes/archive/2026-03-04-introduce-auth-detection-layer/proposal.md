## Why

当前任务执行链路里的鉴权失败识别仍然依赖 `base_execution_adapter.py` 中少量全局 regex，既无法稳定覆盖 `opencode` 这类多 provider、结构化错误包装的场景，也容易让真实鉴权失败在编排阶段被误判为普通失败或 `waiting_user`。随着各 engine 持续演进，继续把模式硬编码在执行适配器里会让规则升级成本越来越高，因此需要把鉴权失败识别提升为一层独立、可扩展、可审计的运行时能力。

## What Changes

- 新增独立的 `auth_detection` 运行时层，在 adapter 执行结束后、generic `waiting_user` 推断之前执行鉴权失败检测。
- 采用“Python engine-specific detector + YAML rule pack”混合模型：Python 负责结构化提取和引擎专用归一化，YAML 负责可升级的文本/字段匹配与分类映射。
- 将 detection 结果统一为内部结构化结果，并落入 attempt 审计产物与诊断记录，供后续调优和客户端鉴权流程使用。
- 将现有 `AUTH_REQUIRED_PATTERNS` 降级为 legacy fallback，不再作为规则扩展主路径。
- 以现有 fixture 样本为第一版规则基线，覆盖 `opencode` 结构化强规则、`codex/gemini/iflow` 文本强规则、`iflowcn` 问题样本层和保守兜底层。

## Capabilities

### New Capabilities
- `auth-detection-layer`: 定义后台非交互执行模式下的鉴权失败检测层、规则架构、结构化结果和内部审计要求。

### Modified Capabilities
- `engine-execution-failfast`: 将 `AUTH_REQUIRED` 失败归类来源扩展为 `auth_detection` 层，并约束高/中/低置信度对失败分类的影响。
- `interactive-run-lifecycle`: 在 generic `waiting_user` 推断前引入 auth detection，并约束高置信度鉴权命中优先于等待态推断。
- `engine-adapter-runtime-contract`: 明确 adapter/runtime parse 必须暴露可供 auth detection 使用的原始证据和结构化材料。

## Impact

- 影响代码主要位于 `server/runtime/adapter/*`、`server/runtime/auth_detection/*`、`server/services/orchestration/*`、`server/runtime/observability/*` 与各引擎的 auth 子目录。
- 新增 YAML 规则包和 JSON Schema 作为内部规则资产，不新增外部依赖。
- 不修改 HTTP API，也不修改对外 runtime/FCMP schema；变化仅限内部编排判定与 `.audit/*` 审计材料。
