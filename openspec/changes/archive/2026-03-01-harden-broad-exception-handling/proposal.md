## Why

代码库中存在大量 `except Exception`（当前基线约 231 处），且部分场景出现 `pass`、循环吞没或无结构化诊断信息，导致根因定位成本高、故障可观测性不足。需要在不破坏现有行为的前提下建立统一异常处理分层策略，并增加门禁防止回归。

## What Changes

- 全量盘点并分层治理 `except Exception`：
  - 可安全收窄的场景改为具体异常类型（如 `TypeError/ValueError/JSONDecodeError/OSError`）。
  - 保留 broad catch 的场景必须有明确策略归类（边界映射、best-effort cleanup、观测附加、第三方边界）。
- 建立 machine-readable 白名单基线，记录当前批准的 broad catch 分布与分类统计。
- 新增 AST 门禁测试，阻止新增未授权 broad catch（文件级和分类计数）。
- 对核心链路（orchestration/runtime）优先处理高风险吞没（`pass`/`continue`/`silent return`）并补强日志可诊断性。

## Capabilities

### New Capabilities
- `exception-handling-hardening`: 宽泛异常处理治理与门禁能力，确保 broad catch 可审计、可追踪、可逐步收敛。

### Modified Capabilities
- _None._

## Impact

- Affected code:
  - `server/routers/*`
  - `server/services/*`
  - `server/runtime/*`
  - `server/engines/*`
  - `tests/unit/*`（新增策略门禁测试）
  - `docs/contracts/*`（新增异常白名单合同）
- Public API: 无 breaking change。
- Runtime schema/invariants: 不修改。
- Tooling: 依赖现有 pytest + AST 分析，不新增外部 lint 依赖。
