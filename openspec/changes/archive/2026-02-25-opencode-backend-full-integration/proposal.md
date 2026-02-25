## Why

`opencode` 在此前变更中仅以 capability-unavailable 占位接入，无法进入正式执行链路。本轮已完成从占位到正式后端的全链路实现（执行、interactive 续跑、管理/升级、UI 内联终端、缓存与文件忽略规则、文档与测试）。

当前缺少对应的 OpenSpec change 记录，会导致“实现已完成但规格演进路径缺失”的治理漂移；需要补齐一个可追踪的 change，明确本轮行为收敛点与验收范围。

## Dependencies

- `2026-02-23-interactive-42-engine-runtime-adapter-decoupling`
- `2026-02-23-interactive-41-external-runtime-harness-conformance`
- `2026-02-13-engine-management-ui-upgrade`

## What Changes

1. 将 `opencode` 从临时占位升级为正式 Adapter，实现 start/resume 命令构建、进程执行、runtime 流解析与 session handle 提取。
2. interactive 续跑基线固定为 `opencode run --session=<id> --format json --model <provider/model> '<message>'`。
3. 模型治理改为 `opencode models` 动态探测 + 本地缓存，不再依赖手工维护 `manifest/snapshot` 作为 opencode 的主路径。
4. 模型缓存采用后台异步刷新（启动后、定时、每次 opencode run/resume 后触发），接口读取缓存不阻塞请求。
5. 管理/升级链路纳入 `opencode`：安装探测、版本检测、升级入口、脚本参数枚举同步。
6. 运行环境注入 XDG 目录映射，保证 opencode 鉴权与配置文件路径可预测，并兼容手工复制鉴权文件的运维方式。
7. `AgentCliManager` 补齐 opencode 基线配置与凭据导入规则：
   - `agent_config/opencode/auth.json` -> `~/.local/share/opencode/auth.json`
   - `agent_config/opencode/antigravity-accounts.json` -> `~/.config/opencode/antigravity-accounts.json`
8. `/ui/engines` 新增 `opencode` 内联终端 command profile；执行表单模型选择升级为 provider/model 双下拉（兼容旧 `model` 字段提交）。
9. 文档与测试同步更新，覆盖 adapter、模型探测缓存、鉴权映射、管理 API、UI 与回归场景。

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
- `external-runtime-harness-cli`
- `engine-upgrade-management`
- `management-api-surface`
- `runtime-environment-parity`
- `ui-engine-inline-terminal`
- `ui-engine-management`
- `skill-package-validation-schema`

## Impact

- Affected code:
  - `server/adapters/opencode_adapter.py`
  - `server/services/model_registry.py`
  - `server/services/agent_cli_manager.py`
  - `server/services/engine_upgrade_manager.py`
  - `scripts/agent_manager.py`
  - `server/services/ui_shell_manager.py`
  - `server/services/cache_key_builder.py`
  - `server/services/job_orchestrator.py`
  - `agent_harness/storage.py`
  - `server/assets/schemas/skill_runner_manifest.schema.json`
  - `server/assets/models/opencode/*`
- Affected APIs/UI:
  - `/ui/engines` 命令列表新增 `opencode`
  - interactive resume 行为对 `opencode` 转为正式 session 续跑
- Affected tests/docs:
  - adapter/model/management/UI/cache/harness 相关单测与回归测试
  - 引擎列表、执行流程与开发说明文档
