## Context

当前服务层、运行时层、引擎适配层广泛使用 `except Exception`。其中一部分属于边界映射或清理兜底，但也存在吞没风险（`pass`、`continue`、隐式返回）。在不改变外部行为的约束下，需要建立一套可审计、可渐进收敛的治理机制，并立即阻止回归。

## Goals / Non-Goals

**Goals:**
- 建立 `except Exception` 的白名单基线与策略合同（machine-readable）。
- 通过 AST 测试把“新增未授权 broad catch”变为门禁失败。
- 在核心模块中先完成可安全收窄（类型转换、JSON/I/O 解析等）。
- 保持兼容：不改变 HTTP API、runtime 合同、statechart 不变量。

**Non-Goals:**
- 不在本次 change 内完成所有 broad catch 的彻底移除。
- 不引入新的 lint 工具链依赖（先用 pytest + AST）。
- 不借此改动业务流程语义（只做异常处理治理和可观测性增强）。

## Decisions

### 1) 采用“白名单基线 + 计数门禁”策略
- 使用 `docs/contracts/exception_handling_allowlist.yaml` 作为基线。
- 记录每个文件 broad catch 分类计数（`total/pass/loop_control/return/log/other`）。
- 门禁测试要求“实际计数不得高于基线，且不得出现未登记文件”。

### 2) 异常处理分层模型
- 边界层（routers/adapter入口）：允许 broad catch 做错误映射，但必须可诊断。
- 业务核心层（services/runtime核心）：优先改具体异常，避免吞没。
- 清理层（cleanup/finalizer）：允许 best-effort broad catch，但需要保留可追踪上下文。

### 3) 可安全收窄优先规则
- `int()/float()/枚举转换`：`Exception -> (TypeError, ValueError)`。
- `json.loads/read_text`：`Exception -> (JSONDecodeError, OSError, ValueError)`（按上下文裁剪）。
- 模型校验：`Exception -> ValidationError`（如 pydantic validate 路径）。

### 4) 兼容优先
- 保留必要 broad catch 的语义，不主动改变成功/失败分支。
- 通过策略文件显式批准保留项，后续分批继续收敛。

## Risks / Trade-offs

- [Risk] 一次性全量收窄可能带来行为回归。  
  → Mitigation: 先建立门禁和基线，再分批收窄可确定场景。

- [Risk] 白名单过大导致“形式合规、实质未改”。  
  → Mitigation: 以分类计数追踪，后续 change 逐批降低基线。

- [Risk] AST 分类与运行时语义可能存在偏差。  
  → Mitigation: 门禁只做结构约束；行为正确性由现有回归测试覆盖。

## Migration Plan

1. 创建 OpenSpec artifacts（proposal/specs/design/tasks）。
2. 新增异常治理合同文件（allowlist baseline）。
3. 新增 AST 门禁测试并纳入单元测试执行集。
4. 对 core 模块落第一批可安全收窄改造。
5. 运行指定回归测试，确认兼容。
6. 在 tasks 中记录下一轮基线收敛计划。

## Open Questions

- 是否在后续 change 引入更细粒度“行级白名单 + 注释强制”策略（当前先采用文件级分类计数）。
