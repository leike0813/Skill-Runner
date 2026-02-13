## Context

问题根因是安装更新分支的入口条件过宽：`live_skill_dir.exists()`。
这会把“无效目录”误判为“可更新 skill”。

## Decisions

### 1) 已安装判定收紧

- 新增 `SkillPackageManager._get_installed_version_if_valid()`：
  - 目录不存在 -> `None`
  - 目录存在但版本读取失败 -> `None`（并记录 warning）
  - 目录有效 -> 返回已安装版本

仅当返回版本时才进入 update 分支。

### 2) 无效目录隔离

- 若目标目录存在但无有效版本，先迁移到：
  - `skills/.invalid/<skill_id>-<utc_timestamp>[-n]`
- 然后执行 fresh install。
- 这样可保留现场，避免静默覆盖，便于审计与回溯。

### 3) 测试用 demo skill 改为临时上传执行

不再引入运行时固定过滤清单，而是把 demo skill 从 `skills/` 迁移到 `tests/fixtures/skills/`，并通过临时 skill 机制在测试时按需上传。

实现策略：

1. suite 扩展：
   - `skill_source`: `installed | temp`（默认 `installed`）
   - `skill_fixture`: 当 `skill_source=temp` 时，指定 `tests/fixtures/skills/<id>`。
2. integration runner：
   - `installed`：保持原内部编排路径；
   - `temp`：调用 `TempSkillRunManager` 进行解包校验，并使用 `workspace_manager.create_run_for_skill` + `job_orchestrator.run_job(skill_override=...)`。
3. e2e runner：
   - `installed`：保持 `/v1/jobs` 流程；
   - `temp`：走 `/v1/temp-skill-runs` 创建/上传/查询流程。

### 4) 分层保持

- integration 仍不经 HTTP，保留“内部服务编排层”语义；
- e2e 继续通过 HTTP 路由；
- 两者复用同一套 suite 文件，但执行通道不同，避免层级退化为同质测试。
