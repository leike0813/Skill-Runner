## Overview

本 change 采用三条并行收口线：

1. 运行参数层硬切移除 `debug`，但 bundle 服务层不变。
2. 通过单独的 shell wrapper 提供“宿主机 -> docker compose exec api -> 容器内 agent-harness”的正式入口。
3. 以“正式支持面”为标准重组 `scripts/`，先修引用，再迁移文件。

这样可以最小化运行语义风险：run 执行主链路不改，bundle 能力不改，本地 `agent-harness` 语义也不改。

## Runtime Debug Flag Removal

`runtime_options.debug` 当前只在 E2E 示例客户端的 run form、路由解析、options policy 和部分文档/spec 中残留。run bundle 是否为 debug 版本已经由独立下载接口决定，因此运行期开关属于重复设计。

实施方式：

- 从 `options_policy.runtime_options` 移除 `debug`。
- 删除 E2E 表单中的 `Debug mode` checkbox。
- 删除 E2E 路由中对 `runtime__debug` 的采集和 payload 写入。
- 清理对应 locale 文案、测试断言和 API 文档中的旧说明。

不做兼容保留。未知 runtime option 将按现有策略被忽略或拒绝，具体行为沿用现有 options policy 验证链路。

## Harness Container Wrapper

`agent_harness` 当前是本地 CLI，内部直接 `subprocess.run(...)`，不存在远程 transport。要让容器部署用户在宿主机上获得正式入口，最小变更方案是新增 wrapper 脚本，而不是修改 `agent-harness` 本体：

- 新脚本固定使用 `docker compose exec api agent-harness ...`
- 原样透传 argv、stdin、stdout、stderr 和退出码
- 在容器未启动、docker 缺失、compose 子命令缺失时输出明确错误

该脚本是“项目支持的容器入口”，不是新的协议层，也不会改变 `agent_harness` 的 `RuntimeProfile` 解析逻辑。

## Scripts Prune Policy

按“是否属于正式产品/部署/受支持运维入口”分类：

### Keep in `scripts/`

- `agent_manager.py`
- `agent_manager.sh`
- `deploy_local.sh`
- `deploy_local.ps1`
- `entrypoint.sh`
- `entrypoint_e2e.sh`
- `render_release_compose.py`
- `reset_project_data.py`
- `start_ui_auth_server.sh`
- 新增 harness container wrapper

### Move to `deprecated/scripts/`

- `upgrade_agents.sh`
- `check_agent_auth.sh`
- `check_agent_auth.ps1`
- `clear_cache.py`
- `clear_cache_workspace.sh`

这些脚本有历史用途或兼容价值，但不再作为当前项目推荐入口。

### Move to `artifacts/scripts/`

- `probe_auth_lock.py`
- `toggle_agent_auth_state.py`
- `start_e2e_client.sh`

这些脚本主要用于排障、实验或一次性辅助，不应再出现在主脚本目录。

## Spec and Docs Alignment

需要同步的主 specs：

- `builtin-e2e-example-client`
- `job-orchestrator-modularization`
- `external-runtime-harness-cli`
- `local-deploy-bootstrap`

主文档至少同步：

- `README.md` + 多语言 README
- `docs/containerization.md`
- `docs/api_reference.md`

重点说明：

- debug bundle 是独立下载能力
- runtime debug 开关已下线
- 容器部署下 harness 的正式入口是 wrapper，而不是宿主机直接运行 `agent-harness`

## Verification Strategy

- E2E run form / runtime option 测试：确认 `debug` 已移除，主链路不回退。
- Harness wrapper 测试：通过 shell 级 mock/monkeypatch 验证 `docker compose exec api agent-harness` 透传行为。
- 文档/脚本引用检查：确保主目录不再引用被迁移脚本路径。
