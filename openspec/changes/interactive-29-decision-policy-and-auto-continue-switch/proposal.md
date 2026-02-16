## Why

interactive 模式已支持 ask_user/pending/reply，但中间步骤的“问题类型与提问结构”仍缺少统一框架，客户端难以稳定构建回复 UI。  
同时，当前策略默认依赖用户逐步回复，缺少“用户未回复时自动决策继续”的可控开关，不利于不同业务场景切换。

## What Changes

1. 新增“交互决策协议”基础框架：
   - 统一中间问题分类（kind）；
   - 统一 Agent 提问载荷结构；
   - 统一每类问题在自动决策场景下的默认处理策略。

2. 新增 interactive 严格回复开关（默认开启，兼容现状）：
   - `interactive_require_user_reply=true`（默认）：严格等待用户回复；
   - `interactive_require_user_reply=false`：超时后自动决策并继续执行。

3. 明确两类执行档位在 strict on/off 下的行为矩阵：
   - `resumable`：strict on 时停在 `waiting_user`；strict off 时超时后 resume 并自动决策；
   - `sticky_process`：strict on 时超时失败；strict off 时超时向当前进程注入自动决策指令并继续。

4. 增加交互历史审计字段：
   - 标记每次交互是 `user_reply` 还是 `auto_decide_timeout`；
   - 记录自动决策触发时间与触发来源。

5. 补齐 interactive 模式 Skill patch 提示词策略：
   - 自动模式继续注入“默认自动执行”提示词；
   - interactive 模式注入“按统一提问载体发问”的提示词；
   - 仅约束 Agent 提问格式，不约束用户回复格式（用户回复保持自由文本）。

## Capabilities

### New Capabilities
- `interactive-decision-policy`: 定义 interactive 中间步骤的问题分类、Agent 提问结构与自动决策规则。

### Modified Capabilities
- `interactive-job-api`: 增加 strict 开关与交互历史分辨字段（用户回复/自动决策）。
- `interactive-run-lifecycle`: 引入 strict on/off 下的 `waiting_user` 行为分支。
- `interactive-session-timeout-unification`: 将 `session_timeout_sec` 同时用于 strict off 的自动决策触发计时。

## Impact

- `server/models.py`
- `server/services/options_policy.py`
- `server/assets/configs/options_policy.json`
- `server/services/job_orchestrator.py`
- `server/services/run_store.py`
- `server/adapters/base.py`
- `server/services/skill_patcher.py`
- `server/routers/jobs.py`
- `docs/api_reference.md`
- `docs/dev_guide.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_job_orchestrator.py`
- `tests/unit/test_skill_patcher.py`
- `tests/integration/run_integration_tests.py`
