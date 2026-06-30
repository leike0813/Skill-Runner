## 为什么要做

Zotero Agents 插件在提交任务前需要知道当前 Skill-Runner 后端支持哪些执行协议。旧后端没有协议能力接口，插件只能按 legacy 逻辑假定支持 job 协议；新增后端应明确返回能力清单，避免插件误用尚未实现的 sequence workflow。

同时，仓库版本已经出现漂移：最新 tag 为 `v0.7.2`，但 `pyproject.toml` 与 FastAPI metadata 仍是旧值。需要把项目版本收敛到单一事实源，并提供发布前的统一 bump/校验脚本。

## 变更内容

- 新增 `POST /v1/system/handshake`，返回 Zotero Agents handshake response v1。
- 声明 `skillrunner.job.v1` 支持，`skillrunner.sequence.v1` 当前不支持。
- 未知协议返回 `supported=false`，不导致 500。
- 保持 `/v1/system/ping` 只作为可达性探测。
- 将后端版本统一为 `pyproject.toml` 的 `[project].version`，并校准为 `0.7.2`。
- 新增 `scripts/bump_version.py`，支持更新版本与 tag/version 一致性校验。
- 在 tag release workflow 中加入版本一致性校验。

## 影响范围

- 新增 system handshake API。
- 更新后端版本读取路径和 FastAPI metadata。
- 更新 Zotero 插件集成文档、API 文档和发布流程。

## 非目标

- 不实现 `skillrunner.sequence.v1` 的原生 sequence workflow 执行。
- 不改变 `/v1/system/ping` 语义。
- 不引入认证策略变化。
- 不由 bump 脚本创建 tag、提交代码或修改 Git 历史。
