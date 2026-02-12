## Why

当前 Skill-Runner 在为每次运行创建独立 `run_dir` 后，并未将该目录纳入 Agent CLI 的受信任目录管理。  
这会在部分环境中导致工具行为不稳定（权限提示、策略限制、交互阻塞），并且缺少统一的“执行前授权、执行后回收”生命周期控制。

## What Changes

- 为 Codex 与 Gemini 引入 `run_dir` 级别的 trust 生命周期管理：
  - 执行前写入该次 `run_dir` 的 trust 记录
  - 执行后删除该次 `run_dir` 的 trust 记录
- 为 Gemini 增加 `trustedFolders.json` 的创建与格式兜底（不存在时自动创建为对象字典）。
- 在容器初始化阶段，为 `runs` 父目录预置 trust（用于降低首轮执行不确定性）：
  - Codex: 写入 `projects."<runs_parent>".trust_level = "trusted"`
  - Gemini: 写入 `trustedFolders.json` 键值 `"<runs_parent>": "TRUST_FOLDER"`
- iFlow 暂不引入 trust 机制（当前未发现稳定可配置入口），保持现状且不改变执行路径。
- 增加异常与清理兜底逻辑：若执行后回收失败，记录警告并由定时清理任务补偿。

## Capabilities

### New Capabilities
- `run-folder-trust-lifecycle`: 在 job 执行生命周期内对 Codex/Gemini 的 `run_dir` trust 进行插入与回收，确保运行稳定并避免全局配置无限膨胀。
- `trust-config-bootstrap`: 在容器入口初始化中为 Codex/Gemini 创建并维护 trust 配置基础文件与父目录 trust 预置。

### Modified Capabilities
- `job-execution-lifecycle`: 扩展现有执行编排，在 Adapter 调用前后注入 trust 操作与异常兜底策略。

## Impact

- Affected code:
  - `server/adapters/codex_adapter.py`
  - `server/adapters/gemini_adapter.py`
  - 新增/扩展 trust 管理服务（建议：`server/services/run_folder_trust_manager.py`）
  - `server/services/job_orchestrator.py`（执行前后钩子）
  - `scripts/entrypoint.sh`（容器初始化 trust bootstrap）
- Affected docs:
  - `docs/containerization.md`
  - `docs/adapter_design.md` / `docs/execution_flow.md`（按实际落地更新）
- Tests:
  - 新增 trust 生命周期单元测试（插入、删除、文件缺失、格式修复）
  - 新增 orchestrator/adapter 集成级单测（执行前写入、执行后删除、失败兜底）
